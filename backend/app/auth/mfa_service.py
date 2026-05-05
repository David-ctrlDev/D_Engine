"""MFA domain service.

* :func:`start_setup`        — generate secret + QR; row stored with
                               ``verified_at IS NULL``.
* :func:`confirm_setup`      — verify the first user-supplied code, mark
                               method active, mint and return 10 cleartext
                               recovery codes (one-time disclosure).
* :func:`verify_during_login` — second-leg of /auth/login; accepts a TOTP
                               code or an unused recovery code.
* :func:`disable`            — verify password + current TOTP, drop method.
* :func:`regenerate_recovery_codes` — same gate as ``disable``, then re-mint
                               the recovery code set.

All mutating functions flush; the *caller* commits. The endpoint layer
sets ``app.current_user`` / ``app.current_tenant`` GUCs before invoking
these because most reads cross RLS-protected tables (memberships, audit).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from app.auth import audit
from app.auth.errors import (
    InvalidCredentialsError,
    InvalidMFACodeError,
    MFAAlreadyConfiguredError,
    MFANotConfiguredError,
    MFASetupPendingError,
)
from app.auth.models import MFAMethod, MFAMethodType, MFARecoveryCode, User
from app.auth.recovery_codes import generate_recovery_codes
from app.auth.recovery_codes import normalize as normalize_code
from app.auth.totp import (
    decrypt_secret,
    encrypt_secret,
    generate_secret,
    provisioning_uri,
    qr_data_uri,
    verify_code,
)
from app.core import security as crypto
from app.db.rls import set_user_context

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def _get_user(session: AsyncSession, user_id: UUID) -> User:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:  # pragma: no cover - users.id is the JWT subject; absence is a bug
        raise InvalidCredentialsError
    return user


async def _get_active_method(session: AsyncSession, user_id: UUID) -> MFAMethod | None:
    return (
        await session.execute(
            select(MFAMethod).where(
                MFAMethod.user_id == user_id,
                MFAMethod.method_type == MFAMethodType.totp,
                MFAMethod.verified_at.is_not(None),
            )
        )
    ).scalar_one_or_none()


async def _get_pending_method(session: AsyncSession, user_id: UUID) -> MFAMethod | None:
    return (
        await session.execute(
            select(MFAMethod).where(
                MFAMethod.user_id == user_id,
                MFAMethod.method_type == MFAMethodType.totp,
                MFAMethod.verified_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def start_setup(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str]:
    """Begin TOTP enrolment. Returns ``(secret_base32, qr_data_uri_png)``.

    The cleartext secret is shown to the user once (for manual entry into
    authenticators that don't accept QR); the QR data URI is the primary
    interface. Both come from the *same* generated secret — the row's
    ``secret_encrypted`` column is what we use for verification later.
    """
    if await _get_active_method(session, user_id) is not None:
        raise MFAAlreadyConfiguredError

    # Cancel any half-finished prior attempt so the partial unique index on
    # (user_id) WHERE method_type='totp' does not block re-insertion.
    pending = await _get_pending_method(session, user_id)
    if pending is not None:
        await session.delete(pending)
        await session.flush()

    user = await _get_user(session, user_id)
    secret = generate_secret()
    method = MFAMethod(
        user_id=user_id,
        method_type=MFAMethodType.totp,
        secret_encrypted=encrypt_secret(secret),
        verified_at=None,
    )
    session.add(method)

    await audit.log_event(
        session,
        event_type=audit.AUDIT_MFA_SETUP_STARTED,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()

    uri = provisioning_uri(secret, account_name=user.email)
    return secret, qr_data_uri(uri)


# ---------------------------------------------------------------------------
# Confirm setup
# ---------------------------------------------------------------------------


async def _replace_recovery_codes(session: AsyncSession, user_id: UUID) -> list[str]:
    """Drop existing recovery codes (used or unused) and create a fresh set.

    Returns the cleartext codes — only chance to see them.
    """
    await session.execute(
        delete(MFARecoveryCode)
        .where(MFARecoveryCode.user_id == user_id)
        .execution_options(synchronize_session=False)
    )
    cleartexts = generate_recovery_codes()
    for code in cleartexts:
        session.add(
            MFARecoveryCode(
                user_id=user_id,
                code_hashed=crypto.hash_recovery_code(normalize_code(code)),
            )
        )
    await session.flush()
    return cleartexts


async def confirm_setup(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    code: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> list[str]:
    """Verify the user's first TOTP code, mark the method active, return
    recovery codes (cleartext, one-time disclosure)."""
    pending = await _get_pending_method(session, user_id)
    if pending is None:
        raise MFASetupPendingError

    secret = decrypt_secret(pending.secret_encrypted)
    if not verify_code(secret, code):
        await audit.log_event(
            session,
            event_type=audit.AUDIT_MFA_FAILURE,
            user_id=user_id,
            tenant_id=tenant_id,
            ip=ip,
            user_agent=user_agent,
            metadata={"phase": "setup_confirm"},
        )
        await session.flush()
        raise InvalidMFACodeError

    pending.verified_at = datetime.now(UTC)
    recovery_codes = await _replace_recovery_codes(session, user_id)

    await audit.log_event(
        session,
        event_type=audit.AUDIT_MFA_SETUP_COMPLETED,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()
    return recovery_codes


# ---------------------------------------------------------------------------
# Login-time verification (TOTP or recovery code)
# ---------------------------------------------------------------------------


async def verify_during_login(
    session: AsyncSession,
    *,
    user_id: UUID,
    code: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Validate a TOTP code (preferred) or a single-use recovery code.

    Raises :class:`InvalidMFACodeError` on failure. On success it returns
    nothing — the caller proceeds with :func:`auth.service.finish_mfa_login`.
    """
    # The /mfa/verify endpoint is unauthenticated (the mfa_token IS the
    # credential), so no GUC has been set yet. Bind ``app.current_user``
    # now so the audit_log_insert policy accepts our event rows.
    await set_user_context(session, user_id=user_id)
    method = await _get_active_method(session, user_id)
    if method is None:
        raise MFANotConfiguredError

    secret = decrypt_secret(method.secret_encrypted)

    # Try TOTP first; codes are 6 digits and recovery codes are 12+
    # alphanumeric, so the inputs don't realistically collide. Treat the
    # decision as "looks like 6 digits → TOTP, otherwise recovery code".
    stripped = code.strip().replace(" ", "")
    if stripped.isdigit() and len(stripped) == 6:
        if verify_code(secret, stripped):
            await _audit_mfa_success(
                session,
                user_id=user_id,
                ip=ip,
                user_agent=user_agent,
                via="totp",
            )
            return
        await _audit_mfa_failure(session, user_id=user_id, ip=ip, user_agent=user_agent, via="totp")
        raise InvalidMFACodeError

    # Recovery-code path. We iterate the user's unused codes and bcrypt-verify
    # each. Bounded list (10) plus rate-limited endpoint keeps this safe.
    normalized = normalize_code(code)
    candidates = (
        (
            await session.execute(
                select(MFARecoveryCode).where(
                    MFARecoveryCode.user_id == user_id,
                    MFARecoveryCode.used_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for candidate in candidates:
        if crypto.verify_recovery_code(normalized, candidate.code_hashed):
            candidate.used_at = datetime.now(UTC)
            await _audit_mfa_success(
                session,
                user_id=user_id,
                ip=ip,
                user_agent=user_agent,
                via="recovery_code",
            )
            return

    await _audit_mfa_failure(
        session, user_id=user_id, ip=ip, user_agent=user_agent, via="recovery_code"
    )
    raise InvalidMFACodeError


async def _audit_mfa_success(
    session: AsyncSession,
    *,
    user_id: UUID,
    ip: str | None,
    user_agent: str | None,
    via: str,
) -> None:
    # Tenant context is set by the caller (login flow); not all paths
    # have it (e.g. /auth/mfa/verify before tenant resolution).
    await audit.log_event(
        session,
        event_type=audit.AUDIT_MFA_SUCCESS,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"via": via},
    )
    await session.flush()


async def _audit_mfa_failure(
    session: AsyncSession,
    *,
    user_id: UUID,
    ip: str | None,
    user_agent: str | None,
    via: str,
) -> None:
    await audit.log_event(
        session,
        event_type=audit.AUDIT_MFA_FAILURE,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"via": via},
    )
    await session.flush()


# ---------------------------------------------------------------------------
# Disable / regenerate
# ---------------------------------------------------------------------------


async def _gate_with_password_and_totp(
    session: AsyncSession, *, user_id: UUID, password: str, totp_code: str
) -> tuple[User, MFAMethod]:
    """Shared check used by ``disable`` and ``regenerate_recovery_codes``."""
    user = await _get_user(session, user_id)
    if not crypto.verify_password(password, user.hashed_password):
        raise InvalidCredentialsError

    method = await _get_active_method(session, user_id)
    if method is None:
        raise MFANotConfiguredError
    secret = decrypt_secret(method.secret_encrypted)
    if not verify_code(secret, totp_code):
        raise InvalidMFACodeError
    return user, method


async def disable(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    password: str,
    totp_code: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Remove the user's TOTP method and recovery codes (CASCADE)."""
    _, method = await _gate_with_password_and_totp(
        session, user_id=user_id, password=password, totp_code=totp_code
    )
    await session.delete(method)

    await audit.log_event(
        session,
        event_type=audit.AUDIT_MFA_DISABLED,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()


async def regenerate_recovery_codes(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    password: str,
    totp_code: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> list[str]:
    """Replace the user's recovery codes; returns the cleartext set."""
    await _gate_with_password_and_totp(
        session, user_id=user_id, password=password, totp_code=totp_code
    )
    cleartexts = await _replace_recovery_codes(session, user_id)
    await audit.log_event(
        session,
        event_type=audit.AUDIT_RECOVERY_CODES_REGENERATED,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()
    return cleartexts
