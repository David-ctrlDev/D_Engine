"""SQLAlchemy 2.0 models for the LLM-credential domain.

A credential is the encrypted API key for one provider (Anthropic
Claude, OpenAI GPT, Google Gemini, or a local Ollama). It belongs
to a tenant; workspace admins create / rotate / delete them. The
``member_access`` enum + ``llm_credential_grants`` table together
control which non-admin members can pick the credential when
starting a chat.

RLS is wired in the migration. ``api_key_encrypted`` never leaves
the backend — the public Pydantic projection only exposes
metadata (nickname, provider, model_default, member_access).
"""

from __future__ import annotations

# ``datetime`` and ``UTC`` MUST be imported at runtime — SQLAlchemy
# evaluates the string forms of ``Mapped[datetime]`` at class
# creation, and the Python-side ``default=`` callables run too.
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LlmProviderKind(StrEnum):
    anthropic = "anthropic"
    openai = "openai"
    google = "google"
    ollama = "ollama"


class LlmMemberAccess(StrEnum):
    """Who, among the tenant's non-admin members, can use this credential.

    Admins of the tenant always see all credentials, regardless of
    this value — they're the ones who registered them.
    """

    admins_only = "admins_only"
    all_members = "all_members"
    specific_members = "specific_members"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LlmCredential(Base):
    """One encrypted provider credential, plus the metadata the UI needs."""

    __tablename__ = "llm_credentials"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[LlmProviderKind] = mapped_column(
        SAEnum(LlmProviderKind, name="llm_provider_kind", native_enum=True),
        nullable=False,
    )
    nickname: Mapped[str] = mapped_column(String(120), nullable=False)
    # Fernet ciphertext. The plaintext API key is never persisted
    # and only decrypted in-process when the agent loop builds an
    # HTTP request to the provider.
    api_key_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Default model the agent picks when this credential is chosen.
    # The chat UI can later override per conversation if we ship a
    # model picker.
    model_default: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Only meaningful for Ollama / OpenAI-compatible custom hosts.
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    member_access: Mapped[LlmMemberAccess] = mapped_column(
        SAEnum(LlmMemberAccess, name="llm_member_access", native_enum=True),
        default=LlmMemberAccess.admins_only,
        server_default=text("'admins_only'"),
        nullable=False,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "nickname", name="uq_llm_credentials_tenant_id_nickname"),
        Index("ix_llm_credentials_tenant_id", "tenant_id"),
        Index("ix_llm_credentials_created_by", "created_by"),
    )


class LlmCredentialGrant(Base):
    """Per-user grant for ``member_access = 'specific_members'``.

    Same shape as ``DatasetGrant``: granting access only makes sense
    for the ``specific_members`` value, so leftover rows on a
    credential whose access switched to ``all_members`` or
    ``admins_only`` are inert.
    """

    __tablename__ = "llm_credential_grants"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    llm_credential_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("llm_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    granted_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("llm_credential_id", "user_id", name="uq_llm_credential_grants_cred_user"),
        Index("ix_llm_credential_grants_user_id", "user_id"),
        Index("ix_llm_credential_grants_credential_id", "llm_credential_id"),
    )


__all__ = [
    "LlmCredential",
    "LlmCredentialGrant",
    "LlmMemberAccess",
    "LlmProviderKind",
]
