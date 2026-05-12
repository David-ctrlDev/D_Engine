"""LLM-credential service layer.

Mirrors the conventions in ``app.data.service``:

* Every mutating function flushes; the **router** commits.
* RLS gates SELECT visibility automatically; the endpoint layer
  also enforces the admin-only gate for CRUD so the right HTTP
  status comes back (403 instead of a silent zero-row update).
* API keys are encrypted with :mod:`app.core.encryption` (Fernet)
  before they touch the DB and decrypted only when the agent loop
  is about to talk to the provider.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.models import TenantMembership, TenantRole, User
from app.core import encryption
from app.llm.models import LlmCredential, LlmCredentialGrant, LlmMemberAccess, LlmProviderKind
from app.llm.providers import ModelOption, test_credential

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LlmCredentialError(Exception):
    """Root for credential-domain errors."""


class DuplicateNicknameError(LlmCredentialError):
    """A credential with that nickname already exists in the tenant."""


class CredentialNotFoundError(LlmCredentialError):
    """Credential doesn't exist or is invisible to the caller (RLS)."""


class NotAnAdminError(LlmCredentialError):
    """The caller isn't an owner / admin of the tenant."""


# ---------------------------------------------------------------------------
# Role check
# ---------------------------------------------------------------------------


async def is_workspace_admin(session: AsyncSession, *, user_id: UUID, tenant_id: UUID) -> bool:
    """``True`` iff the user has ``owner`` or ``admin`` role in the tenant.

    Mirrors the SECURITY DEFINER ``app_is_workspace_admin`` helper
    that the RLS policies use. Implemented in Python here so the
    endpoint layer can return 403 *before* the failing INSERT
    bounces off RLS with a generic error."""
    row = (
        await session.execute(
            select(TenantMembership.role)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row in (TenantRole.owner, TenantRole.admin)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_credentials(session: AsyncSession) -> list[LlmCredential]:
    """All credentials visible to the caller. RLS filters: admins
    see everything in their tenant, members see only the ones
    shared with them."""
    stmt = select(LlmCredential).order_by(LlmCredential.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_credential(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    provider: LlmProviderKind,
    nickname: str,
    api_key: str,
    model_default: str | None,
    base_url: str | None,
    member_access: LlmMemberAccess,
) -> LlmCredential:
    """Register a new credential. Caller must already be an admin
    (the endpoint enforces this via :func:`is_workspace_admin`)."""
    cred = LlmCredential(
        tenant_id=tenant_id,
        created_by=user_id,
        provider=provider,
        nickname=nickname,
        api_key_encrypted=encryption.encrypt(api_key.encode()),
        model_default=model_default,
        base_url=base_url,
        member_access=member_access,
    )
    session.add(cred)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise DuplicateNicknameError(nickname) from e
    return cred


async def update_credential(
    session: AsyncSession,
    *,
    credential_id: UUID,
    nickname: str | None,
    api_key: str | None,
    model_default: str | None,
    base_url: str | None,
    member_access: LlmMemberAccess | None,
) -> LlmCredential:
    """Patch-style update. Only fields the caller supplied are
    written. ``api_key`` is the only way to rotate the secret."""
    cred = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == credential_id))
    ).scalar_one_or_none()
    if cred is None:
        raise CredentialNotFoundError(str(credential_id))
    if nickname is not None:
        cred.nickname = nickname
    if api_key is not None:
        cred.api_key_encrypted = encryption.encrypt(api_key.encode())
    if model_default is not None:
        cred.model_default = model_default
    if base_url is not None:
        cred.base_url = base_url
    if member_access is not None:
        cred.member_access = member_access
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise DuplicateNicknameError(nickname or "") from e
    return cred


async def delete_credential(session: AsyncSession, *, credential_id: UUID) -> None:
    """Cascade-deletes any grants thanks to the FK constraint."""
    cred = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == credential_id))
    ).scalar_one_or_none()
    if cred is None:
        raise CredentialNotFoundError(str(credential_id))
    await session.delete(cred)
    await session.flush()


# ---------------------------------------------------------------------------
# Test connection (saved credential)
# ---------------------------------------------------------------------------


async def test_saved_credential(
    session: AsyncSession, *, credential_id: UUID
) -> tuple[bool, str | None, tuple[ModelOption, ...]]:
    """Decrypt the credential's API key and ping the provider.

    Stamps the result back onto the row (``last_tested_at`` +
    ``last_test_status`` + ``last_test_error``) so the UI shows
    freshness. The live model list flows back out so the UI can
    refresh its dropdown after a key rotation.
    """
    cred = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == credential_id))
    ).scalar_one_or_none()
    if cred is None:
        raise CredentialNotFoundError(str(credential_id))
    api_key = encryption.decrypt(cred.api_key_encrypted).decode()
    result = await test_credential(cred.provider, api_key=api_key, base_url=cred.base_url)
    cred.last_tested_at = datetime.now(UTC)
    cred.last_test_status = "ok" if result.ok else "error"
    cred.last_test_error = None if result.ok else (result.error or "")[:500]
    await session.flush()
    return result.ok, result.error, result.models


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------


async def list_grants(
    session: AsyncSession, *, credential_id: UUID
) -> list[tuple[LlmCredentialGrant, User]]:
    stmt = (
        select(LlmCredentialGrant, User)
        .join(User, LlmCredentialGrant.user_id == User.id)
        .where(LlmCredentialGrant.llm_credential_id == credential_id)
        .order_by(LlmCredentialGrant.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [(g, u) for g, u in rows]


async def add_grant(
    session: AsyncSession,
    *,
    credential_id: UUID,
    user_id: UUID,
    granted_by: UUID,
) -> LlmCredentialGrant:
    grant = LlmCredentialGrant(
        llm_credential_id=credential_id, user_id=user_id, granted_by=granted_by
    )
    session.add(grant)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        # Already granted, treat as idempotent — re-fetch and return.
        existing = (
            await session.execute(
                select(LlmCredentialGrant).where(
                    LlmCredentialGrant.llm_credential_id == credential_id,
                    LlmCredentialGrant.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        raise e from None
    return grant


async def remove_grant(session: AsyncSession, *, credential_id: UUID, user_id: UUID) -> None:
    grant = (
        await session.execute(
            select(LlmCredentialGrant).where(
                LlmCredentialGrant.llm_credential_id == credential_id,
                LlmCredentialGrant.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if grant is not None:
        await session.delete(grant)
        await session.flush()


__all__ = [
    "CredentialNotFoundError",
    "DuplicateNicknameError",
    "LlmCredentialError",
    "NotAnAdminError",
    "add_grant",
    "create_credential",
    "delete_credential",
    "is_workspace_admin",
    "list_credentials",
    "list_grants",
    "remove_grant",
    "test_saved_credential",
    "update_credential",
]
