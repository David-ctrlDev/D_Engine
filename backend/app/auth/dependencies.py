"""FastAPI dependencies for the auth layer.

These are the building blocks every endpoint composes:

* :func:`request_metadata`        — extract client IP and User-Agent for
                                    audit logging.
* :func:`get_session`             — yield a DB session with no GUCs set
                                    (for public endpoints: register,
                                    verify-email, login, password reset).
* :func:`get_authenticated_session` — same, but also reads the access JWT
                                    from the cookie, validates it, and
                                    sets ``app.current_user`` /
                                    ``app.current_tenant`` GUCs so RLS
                                    applies.
* :func:`get_current_user`        — fetch the user row, requires auth.
* :func:`require_mfa_pending`     — validate a body-supplied
                                    ``mfa_token`` and return the user_id.

Authenticated endpoints depend on :func:`get_authenticated_session`. Public
endpoints depend on :func:`get_session` directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cookies import ACCESS_COOKIE_NAME
from app.auth.models import User
from app.core.tokens import (
    TokenError,
    TokenScope,
    decode_token,
)
from app.db.rls import set_request_context
from app.db.session import async_session_maker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ---------------------------------------------------------------------------
# Request metadata
# ---------------------------------------------------------------------------


class RequestMetadata(BaseModel):
    ip: str | None
    user_agent: str | None


def request_metadata(request: Request) -> RequestMetadata:
    """Extract the client IP and User-Agent for audit-logging.

    Behind a reverse proxy ``request.client.host`` is the proxy. Production
    deploys should configure a trusted proxy and use ``X-Forwarded-For``;
    we intentionally do not honour that header in v0 because trusting it
    by default is a foot-gun.
    """
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return RequestMetadata(ip=ip, user_agent=user_agent)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


async def get_session() -> AsyncIterator[AsyncSession]:
    """Public-endpoint session: no GUCs set, RLS-protected tables return
    nothing on read."""
    async with async_session_maker() as session:
        yield session


# ---------------------------------------------------------------------------
# Authenticated dependencies
# ---------------------------------------------------------------------------


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Cookie"},
    )


class AccessClaims(BaseModel):
    user_id: UUID
    tenant_id: UUID


def _claims_from_access_cookie(token: str | None) -> AccessClaims:
    if not token:
        raise _unauthenticated()
    try:
        payload = decode_token(token, expected_scope=TokenScope.access)
    except TokenError as e:
        raise _unauthenticated() from e
    try:
        return AccessClaims(user_id=UUID(payload["sub"]), tenant_id=UUID(payload["tenant_id"]))
    except (KeyError, ValueError) as e:
        raise _unauthenticated() from e


async def get_authenticated_session(
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE_NAME)] = None,
) -> AsyncIterator[AsyncSession]:
    """Yield a DB session with the request's ``app.current_user`` and
    ``app.current_tenant`` GUCs already set from the access JWT.

    Raises 401 if the cookie is missing, malformed, or expired.
    """
    claims = _claims_from_access_cookie(access_token)
    async with async_session_maker() as session:
        await set_request_context(session, user_id=claims.user_id, tenant_id=claims.tenant_id)
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
AuthSessionDep = Annotated[AsyncSession, Depends(get_authenticated_session)]
RequestMetaDep = Annotated[RequestMetadata, Depends(request_metadata)]


def access_claims(
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE_NAME)] = None,
) -> AccessClaims:
    """Standalone dependency that returns the JWT payload without touching
    the DB session — useful for endpoints that need the user_id but their
    own session-handling (e.g. logout, which sets GUCs after revoking)."""
    return _claims_from_access_cookie(access_token)


AccessClaimsDep = Annotated[AccessClaims, Depends(access_claims)]


# ---------------------------------------------------------------------------
# Current user (DB row)
# ---------------------------------------------------------------------------


async def get_current_user(
    session: AuthSessionDep,
    claims: AccessClaimsDep,
) -> User:
    user = (
        await session.execute(select(User).where(User.id == claims.user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _unauthenticated()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# MFA pending token (used by /auth/mfa/verify)
# ---------------------------------------------------------------------------


def require_mfa_pending(token: str) -> UUID:
    """Validate a JWT issued by ``/auth/login`` when MFA is required and
    return the bound user_id. Raises 401 on any failure."""
    try:
        payload = decode_token(token, expected_scope=TokenScope.mfa_pending)
    except TokenError as e:
        raise _unauthenticated() from e
    try:
        return UUID(payload["sub"])
    except (KeyError, ValueError) as e:
        raise _unauthenticated() from e
