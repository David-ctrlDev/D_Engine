"""HTTP layer for /api/v1/auth/*.

Each endpoint is a thin shell around the service layer. Endpoints:

* translate request bodies into service arguments,
* catch domain errors and re-raise as ``HTTPException`` via
  :mod:`app.auth.error_mapping`,
* set or clear cookies through :mod:`app.auth.cookies`,
* commit the session at the end (services flush only).

The router is mounted at ``/api/v1/auth`` so URLs are versioned from day
one and the prefix doesn't have to change when (or if) we expose a public
API later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import select

from app.auth import mfa_service, service
from app.auth.cookies import (
    REFRESH_COOKIE_NAME,
    clear_session_cookies,
    set_access_cookie,
    set_refresh_cookie,
)
from app.auth.dependencies import (
    AccessClaimsDep,
    AuthSessionDep,
    CurrentUserDep,
    RequestMetaDep,
    SessionDep,
    require_mfa_pending,
)
from app.auth.email import ConsoleEmailSender, EmailSender
from app.auth.error_mapping import to_http_exception
from app.auth.errors import AuthError
from app.auth.models import Tenant, TenantMembership, User
from app.auth.passwords import WeakPasswordError
from app.auth.schemas import (
    ForgotPasswordRequest,
    LoginMFARequiredResponse,
    LoginRequest,
    LoginSuccessResponse,
    MessageResponse,
    MFAConfirmRequest,
    MFAConfirmResponse,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    SessionInfo,
    SessionListResponse,
    TenantPublic,
    UserPublic,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.core import security as crypto
from app.core.rate_limit import limiter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Email sender — single instance, swappable per request via dependency
# ---------------------------------------------------------------------------


def get_email_sender() -> EmailSender:
    """Override target in tests via FastAPI's dependency_overrides."""
    return ConsoleEmailSender()


EmailSenderDep = Annotated[EmailSender, Depends(get_email_sender)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _membership_or_403(
    session: AsyncSession, *, user_id: UUID, tenant_id: UUID
) -> tuple[TenantMembership, Tenant]:
    membership = (
        await session.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No membership in this workspace.",
        )
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:  # pragma: no cover - membership FK guarantees this
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace not found.")
    return membership, tenant


async def _finalise_session(
    session: AsyncSession,
    response: Response,
    issued: service.IssuedSession,
) -> LoginSuccessResponse:
    """Set cookies, commit, and return the public projection of the user."""
    membership, tenant = await _membership_or_403(
        session, user_id=issued.user_id, tenant_id=issued.tenant_id
    )
    user = (await session.execute(select(User).where(User.id == issued.user_id))).scalar_one()
    await session.commit()
    set_access_cookie(response, issued.access_token)
    set_refresh_cookie(response, issued.refresh_token, issued.refresh_expires_at)
    return LoginSuccessResponse(
        user=UserPublic(id=user.id, email=user.email, is_verified=user.is_verified),
        tenant=TenantPublic(id=tenant.id, slug=tenant.slug, name=tenant.name, role=membership.role),
    )


# ===========================================================================
# Registration
# ===========================================================================


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def register(
    request: Request,  # required by slowapi
    body: RegisterRequest,
    session: SessionDep,
    sender: EmailSenderDep,
    meta: RequestMetaDep,
) -> RegisterResponse:
    del request
    try:
        result = await service.register(
            session,
            email=body.email,
            password=body.password,
            workspace_name=body.workspace_name,
            email_sender=sender,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    except (AuthError, WeakPasswordError) as exc:
        raise to_http_exception(exc) from exc
    await session.commit()
    return RegisterResponse(
        user_id=result.user_id,
        tenant_id=result.tenant_id,
        tenant_slug=result.tenant_slug,
    )


# ===========================================================================
# Email verification
# ===========================================================================


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    body: VerifyEmailRequest,
    session: SessionDep,
    meta: RequestMetaDep,
) -> VerifyEmailResponse:
    try:
        user_id = await service.verify_email(
            session, token=body.token, ip=meta.ip, user_agent=meta.user_agent
        )
    except AuthError as exc:
        raise to_http_exception(exc) from exc
    await session.commit()
    return VerifyEmailResponse(user_id=user_id)


# ===========================================================================
# Login + MFA verify
# ===========================================================================


@router.post(
    "/login",
    response_model=LoginSuccessResponse | LoginMFARequiredResponse,
)
@limiter.limit("20/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    session: SessionDep,
    meta: RequestMetaDep,
) -> LoginSuccessResponse | LoginMFARequiredResponse:
    del request
    try:
        result = await service.login(
            session,
            email=body.email,
            password=body.password,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    except AuthError as exc:
        raise to_http_exception(exc) from exc

    if isinstance(result, service.MFAChallenge):
        await session.commit()
        return LoginMFARequiredResponse(mfa_token=result.mfa_token)
    return await _finalise_session(session, response, result)


@router.post("/mfa/verify", response_model=LoginSuccessResponse)
@limiter.limit("10/minute")
async def mfa_verify(
    request: Request,
    body: MFAVerifyRequest,
    response: Response,
    session: SessionDep,
    meta: RequestMetaDep,
) -> LoginSuccessResponse:
    del request
    user_id = require_mfa_pending(body.mfa_token)
    try:
        await mfa_service.verify_during_login(
            session,
            user_id=user_id,
            code=body.code,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
        issued = await service.finish_mfa_login(
            session, user_id=user_id, ip=meta.ip, user_agent=meta.user_agent
        )
    except AuthError as exc:
        raise to_http_exception(exc) from exc
    return await _finalise_session(session, response, issued)


# ===========================================================================
# Refresh + logout
# ===========================================================================


@router.post("/refresh", response_model=MessageResponse)
async def refresh(
    response: Response,
    session: SessionDep,
    meta: RequestMetaDep,
    refresh_cookie: RefreshCookie = None,
) -> MessageResponse:
    """Rotate the refresh token. Reads the cookie set on login."""
    try:
        issued = await service.refresh(
            session,
            refresh_cleartext=refresh_cookie or "",
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    except AuthError as exc:
        clear_session_cookies(response)
        raise to_http_exception(exc) from exc
    set_access_cookie(response, issued.access_token)
    set_refresh_cookie(response, issued.refresh_token, issued.refresh_expires_at)
    await session.commit()
    return MessageResponse(message="Session refreshed.")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    claims: AccessClaimsDep,
    session: SessionDep,
    meta: RequestMetaDep,
    refresh_cookie: RefreshCookie = None,
) -> MessageResponse:
    await service.logout(
        session,
        refresh_cleartext=refresh_cookie,
        user_id=claims.user_id,
        tenant_id=claims.tenant_id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    await session.commit()
    clear_session_cookies(response)
    return MessageResponse(message="Logged out.")


# ===========================================================================
# /auth/me
# ===========================================================================


@router.get("/me", response_model=LoginSuccessResponse)
async def me(
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    session: AuthSessionDep,
) -> LoginSuccessResponse:
    membership, tenant = await _membership_or_403(
        session, user_id=user.id, tenant_id=claims.tenant_id
    )
    return LoginSuccessResponse(
        user=UserPublic(id=user.id, email=user.email, is_verified=user.is_verified),
        tenant=TenantPublic(id=tenant.id, slug=tenant.slug, name=tenant.name, role=membership.role),
    )


# ===========================================================================
# Password reset
# ===========================================================================


@router.post("/password/forgot", response_model=MessageResponse)
@limiter.limit("5/hour")
async def password_forgot(
    request: Request,
    body: ForgotPasswordRequest,
    session: SessionDep,
    sender: EmailSenderDep,
    meta: RequestMetaDep,
) -> MessageResponse:
    del request
    await service.request_password_reset(
        session,
        email=body.email,
        email_sender=sender,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    await session.commit()
    return MessageResponse(
        message="If that email is registered, a password reset link has been sent."
    )


@router.post("/password/reset", response_model=MessageResponse)
async def password_reset(
    body: ResetPasswordRequest,
    session: SessionDep,
    meta: RequestMetaDep,
) -> MessageResponse:
    try:
        await service.reset_password(
            session,
            token=body.token,
            new_password=body.new_password,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    except (AuthError, WeakPasswordError) as exc:
        raise to_http_exception(exc) from exc
    await session.commit()
    return MessageResponse(message="Password updated. Please log in again.")


# ===========================================================================
# MFA setup / disable
# ===========================================================================


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    session: AuthSessionDep,
    meta: RequestMetaDep,
) -> MFASetupResponse:
    try:
        secret, qr_uri = await mfa_service.start_setup(
            session,
            user_id=user.id,
            tenant_id=claims.tenant_id,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    except AuthError as exc:
        raise to_http_exception(exc) from exc
    await session.commit()
    return MFASetupResponse(secret=secret, qr_data_uri=qr_uri)


@router.post("/mfa/setup/confirm", response_model=MFAConfirmResponse)
async def mfa_setup_confirm(
    body: MFAConfirmRequest,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    session: AuthSessionDep,
    meta: RequestMetaDep,
) -> MFAConfirmResponse:
    try:
        codes = await mfa_service.confirm_setup(
            session,
            user_id=user.id,
            tenant_id=claims.tenant_id,
            code=body.code,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    except AuthError as exc:
        raise to_http_exception(exc) from exc
    await session.commit()
    return MFAConfirmResponse(recovery_codes=codes)


@router.post("/mfa/disable", response_model=MessageResponse)
async def mfa_disable(
    body: MFADisableRequest,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    session: AuthSessionDep,
    meta: RequestMetaDep,
) -> MessageResponse:
    try:
        await mfa_service.disable(
            session,
            user_id=user.id,
            tenant_id=claims.tenant_id,
            password=body.password,
            totp_code=body.code,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    except AuthError as exc:
        raise to_http_exception(exc) from exc
    await session.commit()
    return MessageResponse(message="Multi-factor authentication disabled.")


# ===========================================================================
# Sessions list / revoke
# ===========================================================================


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user: CurrentUserDep,
    session: AuthSessionDep,
    refresh_cookie: RefreshCookie = None,
) -> SessionListResponse:
    rows = await service.list_active_sessions(session, user_id=user.id)
    current_hash = crypto.hmac_token(refresh_cookie) if refresh_cookie else None
    return SessionListResponse(
        sessions=[
            SessionInfo(
                id=row.id,
                created_at=row.created_at,
                expires_at=row.expires_at,
                user_agent=row.user_agent,
                ip=row.ip,
                is_current=(current_hash is not None and row.token_hashed == current_hash),
            )
            for row in rows
        ]
    )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: UUID,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    session: AuthSessionDep,
    meta: RequestMetaDep,
) -> MessageResponse:
    changed = await service.revoke_session(
        session,
        user_id=user.id,
        tenant_id=claims.tenant_id,
        refresh_token_id=session_id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    await session.commit()
    if not changed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return MessageResponse(message="Session revoked.")
