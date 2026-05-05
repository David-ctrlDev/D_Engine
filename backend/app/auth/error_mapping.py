"""Map domain-level auth errors to HTTP responses.

Keeping this in one place lets endpoints stay narrow (``raise FooError``)
and gives security review a single audit point for what becomes which
HTTP status code.

Two principles guide the choices below:

1. **Don't leak presence**. Bad password and unknown email both return 401
   with the same body. Same for "expired token" vs "used token" on the
   verify-email path — both come back as a single "invalid or expired
   link" message.
2. **422 is for user-fixable input** (weak password, malformed body),
   **401 is for credentials**, **404 is for missing resources the user
   has access to**, **403 is for resources the user doesn't**.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.auth.errors import (
    AccountInactiveError,
    AccountUnverifiedError,
    AuthError,
    AuthTokenAlreadyUsedError,
    AuthTokenExpiredError,
    AuthTokenInvalidError,
    EmailAlreadyTakenError,
    InvalidCredentialsError,
    InvalidMFACodeError,
    MFAAlreadyConfiguredError,
    MFANotConfiguredError,
    MFASetupPendingError,
    NoMembershipError,
    RefreshTokenExpiredError,
    RefreshTokenInvalidError,
    RefreshTokenReuseError,
)
from app.auth.passwords import WeakPasswordError


def to_http_exception(exc: AuthError | WeakPasswordError) -> HTTPException:
    """Translate a domain exception into the HTTPException the endpoint
    should raise. Centralises status codes and user-facing strings."""
    # ---- 401 — credentials ------------------------------------------------
    if isinstance(exc, InvalidCredentialsError):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if isinstance(exc, RefreshTokenInvalidError | RefreshTokenExpiredError):
        return HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please log in again."
        )
    if isinstance(exc, RefreshTokenReuseError):
        return HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Session anomaly detected. All sessions revoked; please log in again.",
        )

    # ---- 403 — account state ---------------------------------------------
    if isinstance(exc, AccountInactiveError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is inactive.")
    if isinstance(exc, AccountUnverifiedError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox for the verification link.",
        )
    if isinstance(exc, NoMembershipError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="No workspace membership found for this account.",
        )

    # ---- 400 — token state (collapsed to one message; see module docstring)
    if isinstance(
        exc,
        AuthTokenInvalidError | AuthTokenExpiredError | AuthTokenAlreadyUsedError,
    ):
        return HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="This link is invalid or has already been used.",
        )

    # ---- MFA -------------------------------------------------------------
    if isinstance(exc, InvalidMFACodeError):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication code.")
    if isinstance(exc, MFANotConfiguredError):
        return HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Multi-factor authentication is not enabled for this account.",
        )
    if isinstance(exc, MFAAlreadyConfiguredError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Multi-factor authentication is already enabled.",
        )
    if isinstance(exc, MFASetupPendingError):
        return HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No pending MFA setup found. Start setup before confirming.",
        )

    # ---- 409 — registration collisions ----------------------------------
    if isinstance(exc, EmailAlreadyTakenError):
        return HTTPException(status.HTTP_409_CONFLICT, detail="This email is already registered.")

    # ---- 422 — validation ------------------------------------------------
    if isinstance(exc, WeakPasswordError):
        detail: dict[str, object] = {"message": str(exc)}
        if exc.suggestions:
            detail["suggestions"] = exc.suggestions
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)

    # Unhandled domain error: surface a generic 500 rather than leaking
    # internals. Should not happen — every concrete AuthError has a branch.
    return HTTPException(  # pragma: no cover - exhaustiveness guard
        status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal authentication error."
    )
