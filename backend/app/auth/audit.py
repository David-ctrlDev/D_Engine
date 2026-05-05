"""Audit log writer.

Every domain service that changes auth state — registration, login,
logout, MFA setup, password change — calls :func:`log_event` to append a
row to ``audit_log``.

The function is deliberately low-level: callers pass primitives (not
SQLAlchemy objects), and the row is added to the session but not flushed
or committed. The surrounding service decides the transaction boundary,
which lets us batch the audit row into the same commit as the change it
records (so a crash between mutation and audit write is impossible).

RLS responsibility
------------------

The ``audit_log_insert`` policy guarantees ``tenant_id`` matches the
active GUC (or is ``NULL``) and ``user_id`` likewise. Callers may pass
``tenant_id=None`` for events that happen before tenant context exists
(e.g. failed login for an unknown email, registration before the new
tenant is selected as active).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.auth.models import AuditLog

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


# Centralised event-type constants. Using a frozen set rather than an Enum
# keeps the column free-form (we may need to add events from migration
# scripts or operational tools without redeploying the app), but typo-safety
# at the call sites is preserved by importing these symbols.
AUDIT_REGISTER = "register"
AUDIT_EMAIL_VERIFIED = "email_verified"
AUDIT_LOGIN_SUCCESS = "login_success"
AUDIT_LOGIN_FAILURE = "login_failure"
AUDIT_LOGOUT = "logout"
AUDIT_MFA_REQUIRED = "mfa_required"
AUDIT_MFA_SUCCESS = "mfa_success"
AUDIT_MFA_FAILURE = "mfa_failure"
AUDIT_MFA_SETUP_STARTED = "mfa_setup_started"
AUDIT_MFA_SETUP_COMPLETED = "mfa_setup_completed"
AUDIT_MFA_DISABLED = "mfa_disabled"
AUDIT_RECOVERY_CODES_REGENERATED = "recovery_codes_regenerated"
AUDIT_PASSWORD_RESET_REQUESTED = "password_reset_requested"  # noqa: S105  event-name constant
AUDIT_PASSWORD_RESET_COMPLETED = "password_reset_completed"  # noqa: S105  event-name constant
AUDIT_REFRESH = "refresh"
AUDIT_REFRESH_TOKEN_REUSE = "refresh_token_reuse_detected"  # noqa: S105  event-name constant
AUDIT_SESSION_REVOKED = "session_revoked"


async def log_event(
    session: AsyncSession,
    *,
    event_type: str,
    user_id: UUID | None = None,
    tenant_id: UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one row to ``audit_log``. Caller controls flush / commit."""
    session.add(
        AuditLog(
            event_type=event_type,
            user_id=user_id,
            tenant_id=tenant_id,
            ip=ip,
            user_agent=user_agent,
            event_metadata=metadata,
        )
    )
