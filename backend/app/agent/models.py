"""SQLAlchemy 2.0 models for the agent-conversation domain.

A conversation is one chat thread anchored to a single dataset and
pinned to one BYOK credential + model. Messages are append-only.

RLS makes conversations private to their creator (with a workspace-
owner read override). The migration owns the policies; the comments
here only highlight the column-level facts the ORM cares about.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentMessageRole(StrEnum):
    """Whose turn it is in the chat transcript.

    Mirrors the OpenAI / Anthropic convention so when we add streaming
    or tool-use we don't have to rename the column. ``system`` rows
    aren't surfaced in the UI but they let us replay a thread exactly.
    """

    user = "user"
    assistant = "assistant"
    system = "system"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AgentConversation(Base):
    """One chat thread anchored to a dataset."""

    __tablename__ = "agent_conversations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # RESTRICT (not CASCADE): deleting a credential with live
    # conversations is a workflow we want admins to confront
    # explicitly, not a silent data loss.
    credential_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("llm_credentials.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
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
        Index("ix_agent_conversations_tenant_id", "tenant_id"),
        Index("ix_agent_conversations_dataset_id", "dataset_id"),
        Index("ix_agent_conversations_created_by", "created_by"),
        Index("ix_agent_conversations_credential_id", "credential_id"),
    )


class AgentMessage(Base):
    """One append-only turn in a conversation."""

    __tablename__ = "agent_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[AgentMessageRole] = mapped_column(
        SAEnum(AgentMessageRole, name="agent_message_role", native_enum=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # ``{prompt, completion, total}`` for assistant messages, NULL for
    # user / system messages. Optional metric — surfaces "esto costó N
    # tokens" in the UI later. We don't track $ price here; that needs
    # provider-specific rate tables and lives outside this slice.
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_agent_messages_conversation_id", "conversation_id"),
        Index("ix_agent_messages_created_at", "created_at"),
    )


__all__ = ["AgentConversation", "AgentMessage", "AgentMessageRole"]
