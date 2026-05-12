"""RLS invariants for the LLM-credential domain.

Three interesting branches in the ``llm_credentials`` SELECT policy plus
the admin-only INSERT/UPDATE/DELETE gate:

* Cross-tenant invisibility (the foundation).
* ``admins_only``: invisible to plain members, visible to admins.
* ``all_members``: visible to every member of the tenant.
* ``specific_members`` + grant: visible to grantee only.
* INSERT/UPDATE/DELETE: only ``owner`` or ``admin`` role passes RLS.
* ``llm_credential_grants`` SELECT: the grantee can see their own grant
  (no admin gate needed); admins of the credential's tenant can see all
  grants.

If any of these tests ever fail, the BYOK access boundary is broken.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from app.auth.models import TenantRole
from app.core import encryption
from app.db.rls import clear_request_context, set_request_context
from app.llm.models import (
    LlmCredential,
    LlmCredentialGrant,
    LlmMemberAccess,
    LlmProviderKind,
)
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from tests.factories import make_membership, make_tenant, make_user

if TYPE_CHECKING:
    from uuid import UUID

    from app.auth.models import Tenant, User
    from sqlalchemy.ext.asyncio import AsyncSession

PG_INSUFFICIENT_PRIVILEGE = "42501"


# ---------------------------------------------------------------------------
# Fixtures: a workspace with an admin, a member, plus a second tenant
# ---------------------------------------------------------------------------


async def _seed_workspace(
    session: AsyncSession,
) -> tuple[Tenant, User, User, Tenant, User]:
    """Create:

    * tenant_a + owner_a + member_a
    * tenant_b + owner_b

    Mirrors ``test_data_models_rls._seed_workspace`` exactly so the
    credential tests sit on the same scaffolding.
    """
    a_tenant_id = uuid4()
    owner_a_id = uuid4()
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_tenant_id)
    a_tenant = await make_tenant(session, tenant_id=a_tenant_id, name="Acme")
    owner_a = await make_user(session, user_id=owner_a_id, email="owner-a@acme.io")
    await make_membership(session, user=owner_a, tenant=a_tenant, role=TenantRole.owner)
    await session.commit()

    member_a_id = uuid4()
    await set_request_context(session, user_id=member_a_id, tenant_id=a_tenant_id)
    member_a = await make_user(session, user_id=member_a_id, email="member-a@acme.io")
    await session.commit()
    await set_request_context(session, user_id=member_a_id, tenant_id=a_tenant_id)
    await make_membership(session, user=member_a, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    b_tenant_id = uuid4()
    owner_b_id = uuid4()
    await set_request_context(session, user_id=owner_b_id, tenant_id=b_tenant_id)
    b_tenant = await make_tenant(session, tenant_id=b_tenant_id, name="Globex")
    owner_b = await make_user(session, user_id=owner_b_id, email="owner-b@globex.io")
    await make_membership(session, user=owner_b, tenant=b_tenant, role=TenantRole.owner)
    await session.commit()

    await clear_request_context(session)
    await session.commit()
    return a_tenant, owner_a, member_a, b_tenant, owner_b


async def _make_credential(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    creator_id: UUID,
    nickname: str = "claude-prod",
    provider: LlmProviderKind = LlmProviderKind.anthropic,
    member_access: LlmMemberAccess = LlmMemberAccess.admins_only,
) -> LlmCredential:
    cred = LlmCredential(
        tenant_id=tenant_id,
        created_by=creator_id,
        provider=provider,
        nickname=nickname,
        api_key_encrypted=encryption.encrypt(b"sk-test-not-a-real-key"),
        model_default=None,
        base_url=None,
        member_access=member_access,
    )
    session.add(cred)
    await session.flush()
    return cred


# ===========================================================================
# Cross-tenant isolation
# ===========================================================================


async def test_cross_tenant_credential_invisible(session: AsyncSession) -> None:
    """A credential created in tenant B is invisible to tenant A's admin."""
    a_tenant, owner_a, _, b_tenant, owner_b = await _seed_workspace(session)
    a_id, b_id = a_tenant.id, b_tenant.id
    owner_a_id, owner_b_id = owner_a.id, owner_b.id

    await set_request_context(session, user_id=owner_b_id, tenant_id=b_id)
    await _make_credential(session, tenant_id=b_id, creator_id=owner_b_id, nickname="b_cred")
    await session.commit()

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    rows = (await session.execute(select(LlmCredential))).scalars().all()
    assert rows == []


# ===========================================================================
# Member-access branches
# ===========================================================================


async def test_admins_only_invisible_to_members(session: AsyncSession) -> None:
    """Default ``admins_only`` — the workspace admin sees it, members do not."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    await _make_credential(
        session,
        tenant_id=a_id,
        creator_id=owner_a_id,
        nickname="admin_only",
        member_access=LlmMemberAccess.admins_only,
    )
    await session.commit()

    # Admin sees it
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    rows = (await session.execute(select(LlmCredential))).scalars().all()
    assert {r.nickname for r in rows} == {"admin_only"}

    # Member doesn't
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    rows = (await session.execute(select(LlmCredential))).scalars().all()
    assert rows == []


async def test_all_members_visible_to_every_tenant_member(session: AsyncSession) -> None:
    """``all_members`` exposes the credential to every member of the tenant."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    await _make_credential(
        session,
        tenant_id=a_id,
        creator_id=owner_a_id,
        nickname="team_credential",
        member_access=LlmMemberAccess.all_members,
    )
    await session.commit()

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    rows = (await session.execute(select(LlmCredential))).scalars().all()
    assert {r.nickname for r in rows} == {"team_credential"}


async def test_specific_members_visible_only_to_grantees(session: AsyncSession) -> None:
    """``specific_members`` + grant: grantee sees the credential, the other
    member without a grant does not."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    # Add a second member, who will not get the grant.
    no_grant_id = uuid4()
    await set_request_context(session, user_id=no_grant_id, tenant_id=a_id)
    no_grant = await make_user(session, user_id=no_grant_id, email="no-grant@acme.io")
    await make_membership(session, user=no_grant, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    # Admin creates the credential and grants it to member_a.
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(
        session,
        tenant_id=a_id,
        creator_id=owner_a_id,
        nickname="shared_specific",
        member_access=LlmMemberAccess.specific_members,
    )
    session.add(
        LlmCredentialGrant(
            llm_credential_id=cred.id,
            user_id=member_a_id,
            granted_by=owner_a_id,
        )
    )
    await session.commit()

    # Grantee can see it
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    rows = (await session.execute(select(LlmCredential))).scalars().all()
    assert {r.nickname for r in rows} == {"shared_specific"}

    # Non-grantee member cannot
    await set_request_context(session, user_id=no_grant_id, tenant_id=a_id)
    rows = (await session.execute(select(LlmCredential))).scalars().all()
    assert rows == []


# ===========================================================================
# Admin gate on writes
# ===========================================================================


async def test_member_cannot_insert_credential(session: AsyncSession) -> None:
    """A plain member tries to register a credential. RLS rejects the INSERT."""
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    session.add(
        LlmCredential(
            tenant_id=a_id,
            created_by=member_a_id,
            provider=LlmProviderKind.anthropic,
            nickname="rogue",
            api_key_encrypted=encryption.encrypt(b"sk-rogue"),
            member_access=LlmMemberAccess.admins_only,
        )
    )
    with pytest.raises(ProgrammingError) as excinfo:
        await session.flush()
    assert excinfo.value.orig.sqlstate == PG_INSUFFICIENT_PRIVILEGE  # type: ignore[union-attr]


async def test_member_cannot_update_credential(session: AsyncSession) -> None:
    """A member who can *see* an ``all_members`` credential still cannot
    UPDATE it — the RLS UPDATE policy requires admin."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(
        session,
        tenant_id=a_id,
        creator_id=owner_a_id,
        nickname="team_cred",
        member_access=LlmMemberAccess.all_members,
    )
    await session.commit()
    cred_id = cred.id

    # Member tries to rename it.
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    from sqlalchemy import update as sql_update

    result = await session.execute(
        sql_update(LlmCredential)
        .where(LlmCredential.id == cred_id)
        .values(nickname="HACKED")
        .execution_options(synchronize_session=False)
    )
    assert result.rowcount == 0  # type: ignore[attr-defined]
    await session.commit()
    session.expire_all()

    # Verify nothing changed (read as admin).
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    fetched = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == cred_id))
    ).scalar_one()
    assert fetched.nickname == "team_cred"


async def test_member_cannot_delete_credential(session: AsyncSession) -> None:
    """Same gate on DELETE — even a credential the member can see is
    undeletable by anyone but an admin."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(
        session,
        tenant_id=a_id,
        creator_id=owner_a_id,
        nickname="team_cred",
        member_access=LlmMemberAccess.all_members,
    )
    await session.commit()
    cred_id = cred.id

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    from sqlalchemy import delete as sql_delete

    result = await session.execute(
        sql_delete(LlmCredential)
        .where(LlmCredential.id == cred_id)
        .execution_options(synchronize_session=False)
    )
    assert result.rowcount == 0  # type: ignore[attr-defined]
    await session.commit()

    # Confirm the credential is still there.
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    fetched = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == cred_id))
    ).scalar_one_or_none()
    assert fetched is not None


async def test_admin_can_update_credential(session: AsyncSession) -> None:
    """Positive control — the admin who created the credential can rotate it."""
    a_tenant, owner_a, _, _, _ = await _seed_workspace(session)
    a_id, owner_a_id = a_tenant.id, owner_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(
        session,
        tenant_id=a_id,
        creator_id=owner_a_id,
        nickname="orig",
    )
    await session.commit()
    cred_id = cred.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    from sqlalchemy import update as sql_update

    result = await session.execute(
        sql_update(LlmCredential)
        .where(LlmCredential.id == cred_id)
        .values(nickname="rotated")
        .execution_options(synchronize_session=False)
    )
    assert result.rowcount == 1  # type: ignore[attr-defined]
    await session.commit()
    # Identity map still holds the pre-update object (conftest uses
    # expire_on_commit=False); force a re-load from the DB.
    session.expire_all()

    # GUCs were scoped to the previous transaction — re-bind before reading.
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    fetched = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == cred_id))
    ).scalar_one()
    assert fetched.nickname == "rotated"


# ===========================================================================
# Grants table: SELECT + INSERT policies
# ===========================================================================


async def test_grant_select_visible_to_grantee(session: AsyncSession) -> None:
    """The grantee can SELECT their own row even though they're not an admin."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(
        session,
        tenant_id=a_id,
        creator_id=owner_a_id,
        nickname="cred",
        member_access=LlmMemberAccess.specific_members,
    )
    session.add(
        LlmCredentialGrant(
            llm_credential_id=cred.id,
            user_id=member_a_id,
            granted_by=owner_a_id,
        )
    )
    await session.commit()

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    grants = (await session.execute(select(LlmCredentialGrant))).scalars().all()
    assert len(grants) == 1
    assert grants[0].user_id == member_a_id


async def test_grant_insert_rejected_for_non_admin(session: AsyncSession) -> None:
    """A non-admin trying to grant themselves access fails the RLS WITH CHECK."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(
        session,
        tenant_id=a_id,
        creator_id=owner_a_id,
        nickname="cred",
        member_access=LlmMemberAccess.specific_members,
    )
    await session.commit()
    cred_id = cred.id

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    session.add(
        LlmCredentialGrant(
            llm_credential_id=cred_id,
            user_id=member_a_id,
            granted_by=member_a_id,
        )
    )
    with pytest.raises(ProgrammingError) as excinfo:
        await session.flush()
    assert excinfo.value.orig.sqlstate == PG_INSUFFICIENT_PRIVILEGE  # type: ignore[union-attr]
