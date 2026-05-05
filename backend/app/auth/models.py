"""SQLAlchemy 2.0 typed declarative models for auth.

Design notes
------------

* **Membership pattern.** A user is identified by a globally-unique email and
  belongs to one or more tenants through ``tenant_memberships``. Roles live on
  the membership, not on the user, so a person can be ``owner`` of one tenant
  and ``member`` of another. In v0 every user has exactly one membership
  (created together with their tenant during registration); the schema is
  ready for invitations without needing a future migration.

* **MFA is per-user, not per-tenant.** ``mfa_methods`` and
  ``mfa_recovery_codes`` belong to a user — TOTP is a property of the human,
  not of any one workspace.

* **Sessions carry tenant context.** ``refresh_tokens`` stores ``tenant_id``
  so a user with multiple memberships can have distinct sessions per
  workspace, and individual workspace sessions can be revoked independently.

* **Single-use tokens** for email verification and password reset live in
  ``auth_tokens``; tokens are stored hashed and removed after use.

* **Audit log** has ``tenant_id`` and ``user_id`` both nullable to capture
  pre-context events (failed logins for non-existent emails, registrations,
  email verifications).

RLS is configured in the migration, not in this module — see
``alembic/versions/0001_initial_auth_schema.py``.
"""

from __future__ import annotations

# `datetime` MUST be imported at runtime (not under TYPE_CHECKING). SQLAlchemy
# 2.0 evaluates the string forms of ``Mapped[datetime]`` at class-creation
# time via ``eval`` — moving it to TYPE_CHECKING raises MappedAnnotationError.
from datetime import datetime  # noqa: TC003
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# ----------------------------------------------------------------------------
# Enums
# ----------------------------------------------------------------------------


class TenantRole(StrEnum):
    """Roles a user can hold within a tenant."""

    owner = "owner"
    admin = "admin"
    member = "member"


class MFAMethodType(StrEnum):
    """Polymorphic discriminator for MFA methods. WebAuthn slots in here later."""

    totp = "totp"


class AuthTokenType(StrEnum):
    """Single-use token kinds; stored hashed."""

    email_verify = "email_verify"
    password_reset = "password_reset"  # noqa: S105  enum discriminator, not a credential


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------


class Tenant(Base):
    """A workspace. Identified by a stable, immutable URL slug."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list[TenantMembership]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class User(Base):
    """A human. Email is globally unique across the platform."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list[TenantMembership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class TenantMembership(Base):
    """The link table between users and tenants — also carries the role."""

    __tablename__ = "tenant_memberships"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[TenantRole] = mapped_column(
        SAEnum(TenantRole, name="tenant_role", native_enum=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    tenant: Mapped[Tenant] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id"),
        Index("ix_tenant_memberships_tenant_id", "tenant_id"),
        Index("ix_tenant_memberships_user_id", "user_id"),
    )


class MFAMethod(Base):
    """A registered second factor. ``verified_at IS NULL`` means setup is pending."""

    __tablename__ = "mfa_methods"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    method_type: Mapped[MFAMethodType] = mapped_column(
        SAEnum(MFAMethodType, name="mfa_method_type", native_enum=True), nullable=False
    )
    secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_mfa_methods_user_id", "user_id"),
        # Partial unique index: at most one TOTP per user. Other method types
        # (e.g., future WebAuthn keys) are unconstrained — a user may register
        # several hardware tokens.
        Index(
            "uq_mfa_methods_user_id_totp",
            "user_id",
            unique=True,
            postgresql_where=text("method_type = 'totp'"),
        ),
    )


class MFARecoveryCode(Base):
    """One-shot fallback codes generated when MFA is activated.

    Codes are stored hashed (bcrypt). Verification iterates the user's unused
    codes and constant-time-compares against each hash — acceptable because
    the recovery flow is rate-limited and the candidate list is bounded (10).
    """

    __tablename__ = "mfa_recovery_codes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hashed: Mapped[str] = mapped_column(String(255), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_mfa_recovery_codes_user_id", "user_id"),)


class RefreshToken(Base):
    """A long-lived session token. Rotated on every refresh.

    The same user may have multiple concurrent sessions across browsers,
    devices, and (when they belong to several tenants) workspaces. Each row
    captures one session.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hashed: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_tenant_id", "tenant_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )


class AuthToken(Base):
    """Single-use tokens for email verification and password reset."""

    __tablename__ = "auth_tokens"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_type: Mapped[AuthTokenType] = mapped_column(
        SAEnum(AuthTokenType, name="auth_token_type", native_enum=True), nullable=False
    )
    token_hashed: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_auth_tokens_user_id", "user_id"),
        Index("ix_auth_tokens_expires_at", "expires_at"),
    )


class AuditLog(Base):
    """Append-only security event log.

    Both ``tenant_id`` and ``user_id`` are nullable so we can capture events
    that happen before tenant/user context exists (e.g., a failed login for
    a non-existent email). On user/tenant deletion we keep the audit row but
    null out the FK so historic events survive account closure.
    """

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_log_tenant_id", "tenant_id"),
        Index("ix_audit_log_user_id", "user_id"),
        Index("ix_audit_log_event_type", "event_type"),
        Index("ix_audit_log_created_at", "created_at"),
    )


__all__ = [
    "AuditLog",
    "AuthToken",
    "AuthTokenType",
    "MFAMethod",
    "MFAMethodType",
    "MFARecoveryCode",
    "RefreshToken",
    "Tenant",
    "TenantMembership",
    "TenantRole",
    "User",
]
