"""Authentication domain service.

Composes the atomic helpers in :mod:`app.core` and :mod:`app.auth` into the
high-level operations the endpoint layer exposes:

* :func:`register`               — create tenant + user + owner membership +
                                   email-verify token, return cleartext token
                                   so the caller can send the email.
* :func:`verify_email`           — consume an email-verify token.
* :func:`request_password_reset` — issue a reset token (silent on unknown
                                   email so we do not leak account existence).
* :func:`reset_password`         — consume a reset token, rotate password,
                                   revoke every existing session.
* :func:`login`                  — verify credentials; return either an MFA
                                   challenge or a fresh access + refresh pair.
* :func:`finish_mfa_login`       — second leg of login when MFA is required.
* :func:`refresh`                — rotate the refresh token, detect reuse.
* :func:`logout`                 — revoke a single refresh token row.

Every mutating function flushes — but the *caller* is responsible for the
transaction boundary (``await session.commit()``). This keeps audit-log
writes inside the same transaction as the change they record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final
from uuid import UUID, uuid4

from sqlalchemy import select, update

from app.auth import audit
from app.auth.email import EmailMessage, EmailSender
from app.auth.errors import (
    AccountInactiveError,
    AccountUnverifiedError,
    AuthTokenAlreadyUsedError,
    AuthTokenExpiredError,
    AuthTokenInvalidError,
    EmailAlreadyTakenError,
    InvalidCredentialsError,
    NoMembershipError,
    RefreshTokenExpiredError,
    RefreshTokenInvalidError,
    RefreshTokenReuseError,
)
from app.auth.models import (
    AuthToken,
    AuthTokenType,
    MFAMethod,
    RefreshToken,
    Tenant,
    TenantMembership,
    TenantRole,
    User,
)
from app.auth.passwords import validate_password_strength
from app.config import settings
from app.core import security as crypto
from app.core.tokens import create_access_token, create_mfa_pending_token
from app.db.rls import set_request_context, set_tenant_context, set_user_context
from app.utils.slug import slug_with_random_suffix, slugify

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegisterResult:
    user_id: UUID
    tenant_id: UUID
    tenant_slug: str
    verify_token: str  # cleartext; the caller emails this and never persists it


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """Fresh credentials returned to a successfully authenticated user."""

    user_id: UUID
    tenant_id: UUID
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True, slots=True)
class MFAChallenge:
    """Login succeeded against the password but MFA is required."""

    user_id: UUID
    mfa_token: str


# ``LoginResult`` could be a typing.Union, but a plain ``|`` annotation
# forces every caller to ``isinstance``-narrow, which is exactly what we
# want at the endpoint layer.
LoginResult = IssuedSession | MFAChallenge


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------


def _verify_email_message(*, email: str, link: str) -> EmailMessage:
    return EmailMessage(
        to=email,
        subject="Verify your email",
        text_body=(
            "Welcome to dataprep.\n\n"
            "Please confirm your email address by clicking the link below:\n\n"
            f"{link}\n\n"
            "If you did not create this account, ignore this email."
        ),
    )


def _password_reset_message(*, email: str, link: str) -> EmailMessage:
    return EmailMessage(
        to=email,
        subject="Reset your password",
        text_body=(
            "We received a request to reset the password on your dataprep account.\n\n"
            "If this was you, click the link below to choose a new password:\n\n"
            f"{link}\n\n"
            "The link expires in one hour. If you did not request this, ignore this email."
        ),
    )


# ---------------------------------------------------------------------------
# Internal token helpers
# ---------------------------------------------------------------------------


def _new_auth_token_row(
    *,
    user_id: UUID,
    token_type: AuthTokenType,
    ttl_seconds: int,
) -> tuple[AuthToken, str]:
    """Mint a single-use token, return ``(row_to_insert, cleartext)``."""
    cleartext = crypto.generate_random_token()
    row = AuthToken(
        user_id=user_id,
        token_type=token_type,
        token_hashed=crypto.hmac_token(cleartext),
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
    )
    return row, cleartext


def _new_refresh_token_row(
    *,
    user_id: UUID,
    tenant_id: UUID,
    ip: str | None,
    user_agent: str | None,
) -> tuple[RefreshToken, str, datetime]:
    cleartext = crypto.generate_random_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.jwt_refresh_ttl_seconds)
    row = RefreshToken(
        user_id=user_id,
        tenant_id=tenant_id,
        token_hashed=crypto.hmac_token(cleartext),
        expires_at=expires_at,
        ip=ip,
        user_agent=user_agent,
    )
    return row, cleartext, expires_at


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def _email_is_taken(session: AsyncSession, email: str) -> bool:
    result = await session.execute(select(User.id).where(User.email == email))
    return result.first() is not None


async def _slug_is_taken(session: AsyncSession, slug: str) -> bool:
    # ``tenants`` is RLS-protected. With no GUCs set the SELECT returns
    # zero rows even for slugs that exist — which would let a registrant
    # silently create a duplicate. We bypass the policy by checking from
    # an admin-side path, but since registration runs as ``dataprep_app``
    # we have to use a different approach: the unique constraint will
    # surface a collision at INSERT time (IntegrityError), so we don't
    # actually need a pre-check. The pre-check here exists only as a
    # best-effort UX hint and must therefore be skippable.
    #
    # The trick: we set the GUC to the slug being tested *as if* it were
    # the active tenant id — but tenants.id is a UUID, not a string, so
    # this won't work. Instead, we accept that we can't easily detect
    # collisions before INSERT and rely on the unique constraint.
    del session, slug
    return False


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    workspace_name: str,
    email_sender: EmailSender,
    ip: str | None = None,
    user_agent: str | None = None,
) -> RegisterResult:
    """Create tenant + user + owner membership + email-verify token."""
    email = email.strip().lower()

    # Strength validation must happen *before* any DB write — and must
    # treat the email + workspace name as user_inputs so zxcvbn penalises
    # passwords built around them.
    validate_password_strength(password, user_inputs=[email, workspace_name])

    if await _email_is_taken(session, email):
        raise EmailAlreadyTakenError(email)

    tenant_id = uuid4()
    user_id = uuid4()

    # RLS WITH CHECK clauses on tenants and tenant_memberships compare the
    # inserted row's id / tenant_id / user_id to the GUCs. We pre-set them
    # to the new IDs so the inserts pass without any bypass.
    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)

    base_slug = slugify(workspace_name) or "workspace"
    slug = base_slug
    # Generate a fresh suffix on retry. The unique constraint on tenants.slug
    # is the source of truth; we just shorten the chance of a retry loop.
    for attempt in range(3):
        del attempt  # unused, kept for clarity
        if not await _slug_is_taken(session, slug):
            break
        slug = slug_with_random_suffix(base_slug)
    else:
        slug = slug_with_random_suffix(base_slug)

    tenant = Tenant(id=tenant_id, name=workspace_name, slug=slug)
    user = User(
        id=user_id,
        email=email,
        hashed_password=crypto.hash_password(password),
        is_active=True,
        is_verified=False,
    )
    membership = TenantMembership(user_id=user_id, tenant_id=tenant_id, role=TenantRole.owner)
    # Flush in dependency order to keep FK violations impossible regardless
    # of SQLAlchemy's topological-sort heuristics (it occasionally orders
    # nullable-FK dependents ahead of their parents inside a single flush).
    session.add(tenant)
    session.add(user)
    await session.flush()
    session.add(membership)
    verify_row, verify_token = _new_auth_token_row(
        user_id=user_id,
        token_type=AuthTokenType.email_verify,
        ttl_seconds=settings.jwt_email_verify_ttl_seconds,
    )
    session.add(verify_row)
    await session.flush()

    await audit.log_event(
        session,
        event_type=audit.AUDIT_REGISTER,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"workspace_slug": slug},
    )
    await session.flush()

    verify_link = f"{str(settings.frontend_url).rstrip('/')}/verify-email?token={verify_token}"
    await email_sender.send(_verify_email_message(email=email, link=verify_link))

    return RegisterResult(
        user_id=user_id, tenant_id=tenant_id, tenant_slug=slug, verify_token=verify_token
    )


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


async def _consume_auth_token(
    session: AsyncSession, *, cleartext: str, expected_type: AuthTokenType
) -> AuthToken:
    """Locate, validate, and mark-used a single-use token row.

    The lookup hashes the supplied cleartext with HMAC-SHA256 and matches on
    that. Constant-time-equality is intrinsic to a hash table lookup over
    a unique index.
    """
    if not cleartext:
        raise AuthTokenInvalidError
    hashed = crypto.hmac_token(cleartext)
    row = (
        await session.execute(
            select(AuthToken).where(
                AuthToken.token_hashed == hashed,
                AuthToken.token_type == expected_type,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise AuthTokenInvalidError
    now = datetime.now(UTC)
    if row.used_at is not None:
        raise AuthTokenAlreadyUsedError
    if row.expires_at < now:
        raise AuthTokenExpiredError
    row.used_at = now
    return row


async def verify_email(
    session: AsyncSession,
    *,
    token: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> UUID:
    """Consume an email-verify token, mark the user verified, return user_id."""
    auth_token = await _consume_auth_token(
        session, cleartext=token, expected_type=AuthTokenType.email_verify
    )
    user_id = auth_token.user_id

    # users has no RLS, so this UPDATE works without GUCs.
    await session.execute(update(User).where(User.id == user_id).values(is_verified=True))

    # The audit row is tenant-aware. Look up the user's only membership in v0
    # (RLS on memberships requires current_user; set it now).
    await set_user_context(session, user_id=user_id)
    membership = (
        await session.execute(
            select(TenantMembership).where(TenantMembership.user_id == user_id).limit(1)
        )
    ).scalar_one_or_none()
    tenant_id = membership.tenant_id if membership else None
    if tenant_id is not None:
        await set_tenant_context(session, tenant_id=tenant_id)

    await audit.log_event(
        session,
        event_type=audit.AUDIT_EMAIL_VERIFIED,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()
    return user_id


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


async def request_password_reset(
    session: AsyncSession,
    *,
    email: str,
    email_sender: EmailSender,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Issue a reset token if the email exists. Silent on unknown emails to
    avoid leaking which addresses are registered."""
    email = email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        # Audit the attempt regardless so brute-forcing addresses is visible.
        await audit.log_event(
            session,
            event_type=audit.AUDIT_PASSWORD_RESET_REQUESTED,
            ip=ip,
            user_agent=user_agent,
            metadata={"email_attempted": email, "user_found": False},
        )
        await session.flush()
        return

    reset_row, cleartext = _new_auth_token_row(
        user_id=user.id,
        token_type=AuthTokenType.password_reset,
        ttl_seconds=settings.jwt_password_reset_ttl_seconds,
    )
    session.add(reset_row)
    await audit.log_event(
        session,
        event_type=audit.AUDIT_PASSWORD_RESET_REQUESTED,
        user_id=user.id,
        ip=ip,
        user_agent=user_agent,
        metadata={"user_found": True},
    )
    await session.flush()

    link = f"{str(settings.frontend_url).rstrip('/')}/reset-password?token={cleartext}"
    await email_sender.send(_password_reset_message(email=email, link=link))


async def _revoke_all_refresh_tokens(session: AsyncSession, *, user_id: UUID) -> int:
    result = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def reset_password(
    session: AsyncSession,
    *,
    token: str,
    new_password: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Consume a reset token, rotate the password, revoke every session."""
    auth_token = await _consume_auth_token(
        session, cleartext=token, expected_type=AuthTokenType.password_reset
    )
    user_id = auth_token.user_id

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        # The token's FK is ondelete=CASCADE, so this would only happen
        # mid-race; treat as invalid.
        raise AuthTokenInvalidError

    validate_password_strength(new_password, user_inputs=[user.email])
    user.hashed_password = crypto.hash_password(new_password)

    await _revoke_all_refresh_tokens(session, user_id=user_id)

    await audit.log_event(
        session,
        event_type=audit.AUDIT_PASSWORD_RESET_COMPLETED,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def _resolve_active_membership(session: AsyncSession, *, user_id: UUID) -> TenantMembership:
    """Return the user's currently-active workspace membership.

    In v0 every user has exactly one membership (created in registration);
    we pick that. When invitations land in a later iteration this picks
    the user's "default" membership and the endpoint layer adds a workspace
    picker for users with multiple memberships.
    """
    await set_user_context(session, user_id=user_id)
    membership = (
        await session.execute(
            select(TenantMembership)
            .where(TenantMembership.user_id == user_id)
            .order_by(TenantMembership.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NoMembershipError(user_id)
    return membership


async def _user_has_active_mfa(session: AsyncSession, *, user_id: UUID) -> bool:
    result = await session.execute(
        select(MFAMethod.id).where(MFAMethod.user_id == user_id, MFAMethod.verified_at.is_not(None))
    )
    return result.first() is not None


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> LoginResult:
    """Verify credentials. Return either an MFA challenge or a fresh session."""
    email = email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    # Always run bcrypt verify, even on a non-existent user, to keep the
    # response time roughly constant. The dummy hash is a real bcrypt
    # value computed once per process; the cost matches a real verify.
    if user is None:
        crypto.verify_password(password, _DUMMY_BCRYPT_HASH)
        await audit.log_event(
            session,
            event_type=audit.AUDIT_LOGIN_FAILURE,
            ip=ip,
            user_agent=user_agent,
            metadata={"email_attempted": email, "reason": "user_not_found"},
        )
        await session.flush()
        raise InvalidCredentialsError

    if not crypto.verify_password(password, user.hashed_password):
        await audit.log_event(
            session,
            event_type=audit.AUDIT_LOGIN_FAILURE,
            user_id=user.id,
            ip=ip,
            user_agent=user_agent,
            metadata={"reason": "bad_password"},
        )
        await session.flush()
        raise InvalidCredentialsError

    if not user.is_active:
        await audit.log_event(
            session,
            event_type=audit.AUDIT_LOGIN_FAILURE,
            user_id=user.id,
            ip=ip,
            user_agent=user_agent,
            metadata={"reason": "inactive"},
        )
        await session.flush()
        raise AccountInactiveError
    if not user.is_verified:
        await audit.log_event(
            session,
            event_type=audit.AUDIT_LOGIN_FAILURE,
            user_id=user.id,
            ip=ip,
            user_agent=user_agent,
            metadata={"reason": "unverified"},
        )
        await session.flush()
        raise AccountUnverifiedError

    if await _user_has_active_mfa(session, user_id=user.id):
        await audit.log_event(
            session,
            event_type=audit.AUDIT_MFA_REQUIRED,
            user_id=user.id,
            ip=ip,
            user_agent=user_agent,
        )
        await session.flush()
        return MFAChallenge(
            user_id=user.id,
            mfa_token=create_mfa_pending_token(user_id=user.id),
        )

    return await _issue_session(session, user_id=user.id, ip=ip, user_agent=user_agent)


_DUMMY_BCRYPT_HASH: Final[str] = crypto.hash_password("dummy-anti-timing-pad")


async def finish_mfa_login(
    session: AsyncSession,
    *,
    user_id: UUID,
    ip: str | None = None,
    user_agent: str | None = None,
) -> IssuedSession:
    """Called by ``/auth/mfa/verify`` after a successful TOTP / recovery code."""
    return await _issue_session(session, user_id=user_id, ip=ip, user_agent=user_agent)


async def _issue_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    ip: str | None,
    user_agent: str | None,
) -> IssuedSession:
    """Mint access + refresh credentials and write the session row."""
    membership = await _resolve_active_membership(session, user_id=user_id)
    tenant_id = membership.tenant_id

    refresh_row, refresh_cleartext, refresh_expires_at = _new_refresh_token_row(
        user_id=user_id, tenant_id=tenant_id, ip=ip, user_agent=user_agent
    )
    session.add(refresh_row)

    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)
    await audit.log_event(
        session,
        event_type=audit.AUDIT_LOGIN_SUCCESS,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()

    return IssuedSession(
        user_id=user_id,
        tenant_id=tenant_id,
        access_token=create_access_token(user_id=user_id, tenant_id=tenant_id),
        refresh_token=refresh_cleartext,
        refresh_expires_at=refresh_expires_at,
    )


# ---------------------------------------------------------------------------
# Refresh token rotation
# ---------------------------------------------------------------------------


async def refresh(
    session: AsyncSession,
    *,
    refresh_cleartext: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> IssuedSession:
    """Rotate the refresh token. Detect reuse of revoked tokens.

    Reuse semantics: if the presented token is in our DB *but already
    revoked*, that's a strong signal someone else captured it (the legit
    client only has the new one we issued the last time). We revoke every
    active session for the user and raise.
    """
    if not refresh_cleartext:
        raise RefreshTokenInvalidError
    hashed = crypto.hmac_token(refresh_cleartext)
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hashed == hashed))
    ).scalar_one_or_none()
    if row is None:
        raise RefreshTokenInvalidError

    now = datetime.now(UTC)
    if row.revoked_at is not None:
        await _revoke_all_refresh_tokens(session, user_id=row.user_id)
        await set_request_context(session, user_id=row.user_id, tenant_id=row.tenant_id)
        await audit.log_event(
            session,
            event_type=audit.AUDIT_REFRESH_TOKEN_REUSE,
            user_id=row.user_id,
            tenant_id=row.tenant_id,
            ip=ip,
            user_agent=user_agent,
        )
        await session.flush()
        raise RefreshTokenReuseError

    if row.expires_at < now:
        raise RefreshTokenExpiredError

    row.revoked_at = now

    new_row, new_cleartext, new_expires_at = _new_refresh_token_row(
        user_id=row.user_id, tenant_id=row.tenant_id, ip=ip, user_agent=user_agent
    )
    session.add(new_row)

    await set_request_context(session, user_id=row.user_id, tenant_id=row.tenant_id)
    await audit.log_event(
        session,
        event_type=audit.AUDIT_REFRESH,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()

    return IssuedSession(
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        access_token=create_access_token(user_id=row.user_id, tenant_id=row.tenant_id),
        refresh_token=new_cleartext,
        refresh_expires_at=new_expires_at,
    )


# ---------------------------------------------------------------------------
# Logout & session listing / revocation
# ---------------------------------------------------------------------------


async def logout(
    session: AsyncSession,
    *,
    refresh_cleartext: str | None,
    user_id: UUID,
    tenant_id: UUID,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Revoke the refresh token presented by the caller.

    A missing cookie is not an error — logout should be idempotent.
    """
    if refresh_cleartext:
        hashed = crypto.hmac_token(refresh_cleartext)
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hashed == hashed,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )

    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)
    await audit.log_event(
        session,
        event_type=audit.AUDIT_LOGOUT,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.flush()


async def list_active_sessions(session: AsyncSession, *, user_id: UUID) -> Iterable[RefreshToken]:
    """Return every non-revoked, non-expired refresh token for ``user_id``."""
    now = datetime.now(UTC)
    result = await session.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.created_at.desc())
    )
    return list(result.scalars())


async def revoke_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    refresh_token_id: UUID,
    ip: str | None = None,
    user_agent: str | None = None,
) -> bool:
    """Revoke a single refresh token by id. Returns whether anything changed."""
    result = await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.id == refresh_token_id,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    rowcount = int(result.rowcount or 0)  # type: ignore[attr-defined]
    if rowcount:
        await set_request_context(session, user_id=user_id, tenant_id=tenant_id)
        await audit.log_event(
            session,
            event_type=audit.AUDIT_SESSION_REVOKED,
            user_id=user_id,
            tenant_id=tenant_id,
            ip=ip,
            user_agent=user_agent,
            metadata={"refresh_token_id": str(refresh_token_id)},
        )
        await session.flush()
    return bool(rowcount)
