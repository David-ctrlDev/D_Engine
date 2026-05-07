"""SQLAlchemy 2.0 models for the data domain.

Conceptual layout
-----------------

A **data source** is a credential or file pointer — the thing that gives us
access to *some* data. Sources are always private to their creator (the
workspace owner has a governance override). Credentials never leave the
creator's hands.

A **dataset** is a logical view *over* a source — a specific table in a
database, or the parsed contents of a file. Datasets carry the visibility
that the user actually cares about: a workspace member shares "the sales
dataset" with their team, not their database password.

A **dataset_grant** lets the creator share a dataset with specific people
(when ``visibility = 'shared_specific'``). When the dataset is
``shared_workspace`` we don't need grants — RLS lets every member of the
tenant in.

A **profile_run** is one execution of the profiler against a dataset. It's
append-only (no UPDATE / DELETE policies) so the history of runs is
preserved as audit-grade evidence.

RLS lives in the migration. Every table here is RLS-enabled and FORCE'd
on; the runtime ``dataprep_app`` role is NOSUPERUSER + NOBYPASSRLS so the
policies actually apply.
"""

from __future__ import annotations

# ``datetime`` MUST be imported at runtime (not under TYPE_CHECKING).
# SQLAlchemy 2.0 evaluates the string forms of ``Mapped[datetime]`` at
# class-creation time via ``eval``.
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# ----------------------------------------------------------------------------
# Enums
# ----------------------------------------------------------------------------


class DataSourceKind(StrEnum):
    """Backing store kinds. ``mssql_azure`` differs from ``mssql`` only in
    the connection string defaults (TLS required, AAD auth optional)."""

    postgres = "postgres"
    mssql = "mssql"
    mssql_azure = "mssql_azure"
    csv = "csv"
    parquet = "parquet"
    xlsx = "xlsx"


class DatasetKind(StrEnum):
    """How the dataset relates to its source.

    * ``table`` — a real table in a SQL database, addressable by
      ``{schema, table}`` in :attr:`Dataset.locator`.
    * ``file_sheet`` — a parsed file or one sheet of a workbook. The
      locator carries the absolute path and (for xlsx) the sheet name.
    * ``query`` — reserved for future iterations; user-supplied SELECT.
    """

    table = "table"
    file_sheet = "file_sheet"
    query = "query"


class DatasetVisibility(StrEnum):
    """Who can SELECT a dataset (writes are always creator + owner).

    * ``private`` — only the creator and the workspace owner.
    * ``shared_workspace`` — every member of the tenant.
    * ``shared_specific`` — the creator, the workspace owner, and every
      user listed in ``dataset_grants``.
    """

    private = "private"
    shared_workspace = "shared_workspace"
    shared_specific = "shared_specific"


class ProfileRunStatus(StrEnum):
    running = "running"
    completed = "completed"
    failed = "failed"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------


class DataSource(Base):
    """A credentialed connection or a stored file. Always private to the
    creator (with a workspace-owner governance override)."""

    __tablename__ = "data_sources"

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
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[DataSourceKind] = mapped_column(
        SAEnum(DataSourceKind, name="data_source_kind", native_enum=True), nullable=False
    )
    # Fernet-encrypted JSON. For DBs: DSN + extra connection options.
    # For files: {path, sha256, size_bytes, original_filename}.
    connection_config_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
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
        UniqueConstraint("tenant_id", "name", name="uq_data_sources_tenant_id_name"),
        Index("ix_data_sources_tenant_id", "tenant_id"),
        Index("ix_data_sources_created_by", "created_by"),
    )


class Dataset(Base):
    """A logical view over a source: a SQL table, a parsed file, or a sheet."""

    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[DatasetKind] = mapped_column(
        SAEnum(DatasetKind, name="dataset_kind", native_enum=True), nullable=False
    )
    # For 'table': {"schema": "public", "table": "customers"}
    # For 'file_sheet': {"path": ".../sales.xlsx", "sheet": "Q1"}
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    inferred_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    row_count_estimate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    visibility: Mapped[DatasetVisibility] = mapped_column(
        SAEnum(DatasetVisibility, name="dataset_visibility", native_enum=True),
        default=DatasetVisibility.private,
        server_default=text("'private'"),
        nullable=False,
    )
    last_introspected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
        UniqueConstraint("tenant_id", "source_id", "name", name="uq_datasets_tenant_source_name"),
        Index("ix_datasets_tenant_id", "tenant_id"),
        Index("ix_datasets_source_id", "source_id"),
        Index("ix_datasets_created_by", "created_by"),
        Index("ix_datasets_visibility", "visibility"),
    )


class DatasetGrant(Base):
    """One row per (dataset, user) when ``visibility = 'shared_specific'``.

    Granting access only makes sense for ``shared_specific``; the policy
    that uses this table additionally checks the parent dataset's
    visibility, so leftover rows on a dataset that switched to private
    are inert.
    """

    __tablename__ = "dataset_grants"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
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
        UniqueConstraint("dataset_id", "user_id", name="uq_dataset_grants_dataset_user"),
        Index("ix_dataset_grants_user_id", "user_id"),
        Index("ix_dataset_grants_dataset_id", "dataset_id"),
    )


class ProfileRun(Base):
    """One execution of the profiler.

    Append-only by design — the migration deliberately omits UPDATE /
    DELETE policies (only the service that owns the row can transition
    its status from ``running`` to ``completed`` / ``failed``).
    """

    __tablename__ = "profile_runs"

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
    status: Mapped[ProfileRunStatus] = mapped_column(
        SAEnum(ProfileRunStatus, name="profile_run_status", native_enum=True),
        default=ProfileRunStatus.running,
        server_default=text("'running'"),
        nullable=False,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_profile_runs_dataset_id", "dataset_id"),
        Index("ix_profile_runs_tenant_id", "tenant_id"),
    )


__all__ = [
    "DataSource",
    "DataSourceKind",
    "Dataset",
    "DatasetGrant",
    "DatasetKind",
    "DatasetVisibility",
    "ProfileRun",
    "ProfileRunStatus",
]
