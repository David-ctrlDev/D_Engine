"""HTTP layer for /api/v1/llm-credentials/* and /api/v1/llm-providers.

Endpoints
---------

* ``GET    /api/v1/llm-providers`` — public catalogue used by the
  "new credential" form (models, docs URLs, whether base_url is
  needed). No auth needed beyond the standard session — every
  signed-in user sees the same catalogue.

* ``GET    /api/v1/llm-credentials`` — list credentials the
  caller can see. Admins see everything in their tenant; members
  see only the ones shared with them (RLS handles the filter).

* ``POST   /api/v1/llm-credentials`` — register a new credential.
  **Admin-only.**
* ``PATCH  /api/v1/llm-credentials/{id}`` — rotate key, change
  nickname, model, access level. **Admin-only.**
* ``DELETE /api/v1/llm-credentials/{id}`` — remove. **Admin-only.**

* ``POST   /api/v1/llm-credentials/test`` — test an *unsaved*
  credential (used by the new-credential form). Any signed-in
  user; the body carries the key.
* ``POST   /api/v1/llm-credentials/{id}/test`` — re-test a saved
  credential. **Admin-only** (the key is decrypted in-process).

* ``GET    /api/v1/llm-credentials/{id}/grants`` — list grants.
  **Admin-only.**
* ``POST   /api/v1/llm-credentials/{id}/grants`` — share with a
  user. **Admin-only.**
* ``DELETE /api/v1/llm-credentials/{id}/grants/{user_id}`` —
  revoke. **Admin-only.**

Admin gate
----------

The check is in Python (via :func:`service.is_workspace_admin`)
*and* in the migration's RLS policies. The Python check gives us
clean 403 responses; the RLS is the actual security boundary —
even if a route forgot the check, the database would refuse the
write because of ``app_is_workspace_admin``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import AccessClaimsDep, AuthSessionDep, CurrentUserDep
from app.llm import providers as provider_catalog
from app.llm import service
from app.llm.models import LlmProviderKind
from app.llm.providers import test_credential
from app.llm.schemas import (
    GrantUserRequest,
    LlmCredentialCreateRequest,
    LlmCredentialGrantPublic,
    LlmCredentialGrantsResponse,
    LlmCredentialListResponse,
    LlmCredentialPublic,
    LlmCredentialUpdateRequest,
    ModelOptionPublic,
    ProviderInfoPublic,
    ProvidersResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["llm"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_only_or_403(condition: bool) -> None:
    if not condition:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores del workspace pueden gestionar credenciales.",
        )


def _provider_to_public(info: provider_catalog.ProviderInfo) -> ProviderInfoPublic:
    return ProviderInfoPublic(
        kind=info.kind,
        display_name=info.display_name,
        description=info.description,
        api_key_docs_url=info.api_key_docs_url,
        needs_base_url=info.needs_base_url,
        default_model=info.default_model,
        models=[ModelOptionPublic(id=m.id, label=m.label, notes=m.notes) for m in info.models],
    )


# ---------------------------------------------------------------------------
# Provider catalogue
# ---------------------------------------------------------------------------


@router.get("/llm-providers", response_model=ProvidersResponse)
async def list_providers(_: CurrentUserDep) -> ProvidersResponse:
    """Static catalogue. Any signed-in user can read it."""
    return ProvidersResponse(
        providers=[
            _provider_to_public(provider_catalog.PROVIDERS[kind])
            for kind in (
                LlmProviderKind.anthropic,
                LlmProviderKind.openai,
                LlmProviderKind.google,
                LlmProviderKind.ollama,
            )
        ]
    )


# ---------------------------------------------------------------------------
# Credentials — list / create / update / delete
# ---------------------------------------------------------------------------


@router.get("/llm-credentials", response_model=LlmCredentialListResponse)
async def list_credentials(session: AuthSessionDep) -> LlmCredentialListResponse:
    creds = await service.list_credentials(session)
    return LlmCredentialListResponse(
        credentials=[LlmCredentialPublic.model_validate(c) for c in creds]
    )


@router.post(
    "/llm-credentials",
    response_model=LlmCredentialPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_credential(
    body: LlmCredentialCreateRequest,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> LlmCredentialPublic:
    _admin_only_or_403(
        await service.is_workspace_admin(session, user_id=user.id, tenant_id=claims.tenant_id)
    )
    try:
        cred = await service.create_credential(
            session,
            tenant_id=claims.tenant_id,
            user_id=user.id,
            provider=body.provider,
            nickname=body.nickname,
            api_key=body.api_key,
            model_default=body.model_default,
            base_url=body.base_url,
            member_access=body.member_access,
        )
    except service.DuplicateNicknameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una credencial con el nombre '{e!s}'.",
        ) from e
    await session.commit()
    return LlmCredentialPublic.model_validate(cred)


@router.patch("/llm-credentials/{credential_id}", response_model=LlmCredentialPublic)
async def update_credential(
    credential_id: str,
    body: LlmCredentialUpdateRequest,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> LlmCredentialPublic:
    from uuid import UUID as _UUID

    try:
        cid = _UUID(credential_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e

    _admin_only_or_403(
        await service.is_workspace_admin(session, user_id=user.id, tenant_id=claims.tenant_id)
    )
    try:
        cred = await service.update_credential(
            session,
            credential_id=cid,
            nickname=body.nickname,
            api_key=body.api_key,
            model_default=body.model_default,
            base_url=body.base_url,
            member_access=body.member_access,
        )
    except service.CredentialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e
    except service.DuplicateNicknameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una credencial con el nombre '{e!s}'.",
        ) from e
    await session.commit()
    return LlmCredentialPublic.model_validate(cred)


@router.delete("/llm-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> None:
    from uuid import UUID as _UUID

    try:
        cid = _UUID(credential_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e
    _admin_only_or_403(
        await service.is_workspace_admin(session, user_id=user.id, tenant_id=claims.tenant_id)
    )
    try:
        await service.delete_credential(session, credential_id=cid)
    except service.CredentialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e
    await session.commit()


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


@router.post("/llm-credentials/test", response_model=TestConnectionResponse)
async def test_unsaved_credential(
    body: TestConnectionRequest, _: CurrentUserDep
) -> TestConnectionResponse:
    """Test a credential *before* saving. Any signed-in user can
    call this — they're sending us a key they already have. We also
    return the live model list so the UI can replace its curated
    dropdown with whatever the provider says this account can use."""
    result = await test_credential(body.provider, api_key=body.api_key, base_url=body.base_url)
    return TestConnectionResponse(
        ok=result.ok,
        error=result.error,
        models=[ModelOptionPublic(id=m.id, label=m.label, notes=None) for m in result.models],
    )


@router.post("/llm-credentials/{credential_id}/test", response_model=TestConnectionResponse)
async def test_saved(
    credential_id: str,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> TestConnectionResponse:
    from uuid import UUID as _UUID

    try:
        cid = _UUID(credential_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e
    _admin_only_or_403(
        await service.is_workspace_admin(session, user_id=user.id, tenant_id=claims.tenant_id)
    )
    try:
        ok, err, live_models = await service.test_saved_credential(session, credential_id=cid)
    except service.CredentialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e
    await session.commit()
    return TestConnectionResponse(
        ok=ok,
        error=err,
        models=[ModelOptionPublic(id=m.id, label=m.label, notes=None) for m in live_models],
    )


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------


@router.get(
    "/llm-credentials/{credential_id}/grants",
    response_model=LlmCredentialGrantsResponse,
)
async def list_grants(
    credential_id: str,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> LlmCredentialGrantsResponse:
    from uuid import UUID as _UUID

    try:
        cid = _UUID(credential_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e
    _admin_only_or_403(
        await service.is_workspace_admin(session, user_id=user.id, tenant_id=claims.tenant_id)
    )
    grants = await service.list_grants(session, credential_id=cid)
    return LlmCredentialGrantsResponse(
        grants=[
            LlmCredentialGrantPublic(
                id=g.id, user_id=u.id, user_email=u.email, granted_at=g.created_at
            )
            for g, u in grants
        ]
    )


@router.post(
    "/llm-credentials/{credential_id}/grants",
    status_code=status.HTTP_201_CREATED,
)
async def add_grant(
    credential_id: str,
    body: GrantUserRequest,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> LlmCredentialGrantPublic:
    from uuid import UUID as _UUID

    from sqlalchemy import select

    from app.auth.models import User as _User

    try:
        cid = _UUID(credential_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e
    _admin_only_or_403(
        await service.is_workspace_admin(session, user_id=user.id, tenant_id=claims.tenant_id)
    )
    grant = await service.add_grant(
        session,
        credential_id=cid,
        user_id=body.user_id,
        granted_by=user.id,
    )
    await session.commit()
    # Re-fetch the user email for the response — the grant row
    # only carries the user_id.
    granted_user = (
        await session.execute(select(_User).where(_User.id == body.user_id))
    ).scalar_one_or_none()
    return LlmCredentialGrantPublic(
        id=grant.id,
        user_id=grant.user_id,
        user_email=granted_user.email if granted_user else "",
        granted_at=grant.created_at,
    )


@router.delete(
    "/llm-credentials/{credential_id}/grants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_grant(
    credential_id: str,
    user_id: str,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> None:
    from uuid import UUID as _UUID

    try:
        cid = _UUID(credential_id)
        uid = _UUID(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada."
        ) from e
    _admin_only_or_403(
        await service.is_workspace_admin(session, user_id=user.id, tenant_id=claims.tenant_id)
    )
    await service.remove_grant(session, credential_id=cid, user_id=uid)
    await session.commit()


__all__ = ["router"]
