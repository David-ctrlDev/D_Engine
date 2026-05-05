"""JWT helpers, scoped per use-case.

Two scopes exist in v0:

* ``access``        — short-lived bearer for API calls. Carries
                      ``sub`` (user_id) and ``tenant_id`` (active workspace).
* ``mfa_pending``   — issued by ``/auth/login`` when MFA is required.
                      Carries only the user_id; very short TTL.

Refresh tokens, email-verify tokens, and password-reset tokens are NOT
JWTs — they are opaque random strings hashed with HMAC-SHA256 and stored
in the database (see :mod:`app.core.security`). That keeps revocation and
single-use semantics straightforward.

HS256 is acceptable for v0; the symmetric secret is ``settings.jwt_secret``.
Production should migrate to RS256 / EdDSA so verifiers don't need the
signing secret.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from jose import ExpiredSignatureError, JWTError, jwt

from app.config import settings


class TokenScope(StrEnum):
    access = "access"
    mfa_pending = "mfa_pending"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TokenError(Exception):
    """Base class for all JWT decode failures."""


class TokenInvalidError(TokenError):
    """Bad signature, malformed token, missing fields, etc."""


class TokenExpiredError(TokenError):
    """The token's ``exp`` claim is in the past."""


class TokenScopeMismatchError(TokenError):
    """A token of the wrong scope was presented to a scoped endpoint."""


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def _encode(*, scope: TokenScope, subject: str, ttl_seconds: int, **extra: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "scope": scope.value,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        "jti": str(uuid4()),
        **extra,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(*, user_id: UUID, tenant_id: UUID) -> str:
    return _encode(
        scope=TokenScope.access,
        subject=str(user_id),
        ttl_seconds=settings.jwt_access_ttl_seconds,
        tenant_id=str(tenant_id),
    )


def create_mfa_pending_token(*, user_id: UUID) -> str:
    return _encode(
        scope=TokenScope.mfa_pending,
        subject=str(user_id),
        ttl_seconds=settings.jwt_mfa_pending_ttl_seconds,
    )


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------


def decode_token(token: str, *, expected_scope: TokenScope) -> dict[str, Any]:
    """Decode ``token`` and verify its scope matches ``expected_scope``.

    Returns the validated payload as a dict. Raises a subclass of
    :class:`TokenError` on any failure.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as e:
        raise TokenExpiredError("token has expired") from e
    except JWTError as e:
        raise TokenInvalidError(str(e)) from e

    actual_scope = payload.get("scope")
    if actual_scope != expected_scope.value:
        raise TokenScopeMismatchError(
            f"expected scope '{expected_scope.value}', got '{actual_scope}'"
        )
    return payload
