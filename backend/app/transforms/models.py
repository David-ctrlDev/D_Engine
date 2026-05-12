"""SQLAlchemy models for the transformation engine.

Two tables:

* :class:`DatasetWorkingCopy` — one mutable draft per dataset+user.
  Carries a pointer to the current parquet snapshot on disk; every
  operation rewrites that snapshot.
* :class:`DatasetOperation` — append-only journal of every transform
  applied to a working copy. Used for the chat result cards, for
  undo, and (later) for a full pipeline replay.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DatasetWorkingCopy(Base):
    """Mutable draft of a dataset that the agent can transform."""

    __tablename__ = "dataset_working_copies"

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
    # Storage-relative path of the current parquet snapshot. The
    # transform engine reads it lazily, writes the new state to a
    # fresh path, and updates this column to point at it.
    snapshot_path: Mapped[str] = mapped_column(String(500), nullable=False)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
        UniqueConstraint("dataset_id", "created_by", name="uq_dataset_working_copies_dataset_user"),
        Index("ix_dataset_working_copies_tenant_id", "tenant_id"),
        Index("ix_dataset_working_copies_dataset_id", "dataset_id"),
    )


class DatasetOperation(Base):
    """One transform applied to a working copy. Append-only."""

    __tablename__ = "dataset_operations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    working_copy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dataset_working_copies.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    op: Mapped[str] = mapped_column(String(64), nullable=False)
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_before_path: Mapped[str] = mapped_column(String(500), nullable=False)
    snapshot_after_path: Mapped[str] = mapped_column(String(500), nullable=False)
    rows_before: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rows_after: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    # ``undone_at`` doubles as the "active vs reverted" flag — undo
    # stamps this column instead of deleting the row, so the audit
    # trail stays intact.
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_dataset_operations_working_copy_id", "working_copy_id"),
        Index("ix_dataset_operations_conversation_id", "conversation_id"),
        Index("ix_dataset_operations_created_at", "created_at"),
    )


__all__ = ["DatasetOperation", "DatasetWorkingCopy"]
