"""Domain-level exceptions raised by the auth service layer.

These are the only exceptions the endpoint layer (layer 6) needs to map
to HTTP responses. Lower-level errors (DB integrity, JWT decode, etc.)
should be caught and re-raised here so the endpoint code stays free of
SQLAlchemy / jose imports.
"""

from __future__ import annotations


class AuthError(Exception):
    """Base class for all domain-level auth failures."""


# ---------------------------------------------------------------------------
# Registration / accounts
# ---------------------------------------------------------------------------


class EmailAlreadyTakenError(AuthError):
    """Registration attempted with an email that already exists globally."""


class AccountInactiveError(AuthError):
    """The account exists but ``is_active`` is false."""


class AccountUnverifiedError(AuthError):
    """The account exists but the user has not verified the email."""


class NoMembershipError(AuthError):
    """The authenticated user has no tenant membership.

    This should not happen in v0 (every user is created together with a
    tenant), but defensively raising lets callers handle a corrupted
    bootstrap rather than crashing on an empty list.
    """


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


class InvalidCredentialsError(AuthError):
    """Email / password mismatch, OR the email simply does not exist.

    The two cases are intentionally indistinguishable to avoid leaking
    information about which addresses are registered.
    """


# ---------------------------------------------------------------------------
# Single-use tokens (email verification, password reset)
# ---------------------------------------------------------------------------


class AuthTokenInvalidError(AuthError):
    """The token is not present or has been tampered with."""


class AuthTokenExpiredError(AuthError):
    """The token's ``expires_at`` is in the past."""


class AuthTokenAlreadyUsedError(AuthError):
    """The token's ``used_at`` is set; single-use tokens cannot be reused."""


# ---------------------------------------------------------------------------
# Refresh tokens (sessions)
# ---------------------------------------------------------------------------


class RefreshTokenInvalidError(AuthError):
    """Refresh cookie missing, malformed, or unknown."""


class RefreshTokenExpiredError(AuthError):
    """Refresh token's ``expires_at`` is in the past."""


class RefreshTokenReuseError(AuthError):
    """A revoked refresh token was presented again — likely an attacker.

    On this error the service revokes every active session for the user.
    """


# ---------------------------------------------------------------------------
# MFA
# ---------------------------------------------------------------------------


class MFAAlreadyConfiguredError(AuthError):
    """Setup attempted while a verified TOTP method already exists."""


class MFANotConfiguredError(AuthError):
    """Operation requires MFA to be active, but no verified method exists."""


class MFASetupPendingError(AuthError):
    """``setup`` produced a row but ``confirm`` was never called.

    Returned when the caller tries to confirm twice or starts setup on a
    user who already has a pending (unverified) method without cancelling
    first.
    """


class InvalidMFACodeError(AuthError):
    """TOTP / recovery code did not validate."""
