"""Request and response schemas for /api/v1/{sources,datasets}.

Mirrors the conventions in ``app/auth/schemas.py``:

* request bodies use a strict model so unknown fields surface as 422,
* responses are minimal projections — they never echo the encrypted
  ``connection_config`` blob,
* enum values come straight from the SQLAlchemy enums so
  serialisation matches the DB literal.

``from __future__ import annotations`` is intentionally *omitted* —
Pydantic v2 evaluates the type annotations at class-creation time.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.data.models import (
    DatasetKind,
    DatasetVisibility,
    DataSourceKind,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class DataSourcePublic(BaseModel):
    """Projection used in list endpoints and as the parent of a dataset.

    Crucially, ``connection_config`` is *not* exposed — that's the
    encrypted blob. The frontend only needs the metadata to render
    the source row.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: DataSourceKind
    created_at: datetime
    last_tested_at: datetime | None
    last_test_status: str | None


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


class DatasetSummary(BaseModel):
    """Row in the dataset list. Light enough to render hundreds at a time."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: DatasetKind
    visibility: DatasetVisibility
    row_count_estimate: int | None
    created_at: datetime
    source_id: UUID
    source_name: str
    source_kind: DataSourceKind


class DatasetColumn(BaseModel):
    """One column of an inferred schema, served straight from
    ``Dataset.inferred_schema['columns']``."""

    name: str
    dtype: str
    nullable: bool
    sample_values: list[str] = Field(default_factory=list)


class DatasetDetail(BaseModel):
    """Detail view for a single dataset.

    ``sample_rows`` is computed on demand by the service from the
    underlying file (it isn't stored in JSONB) so the size of the
    detail response stays bounded.
    """

    id: UUID
    name: str
    kind: DatasetKind
    visibility: DatasetVisibility
    row_count_estimate: int | None
    created_at: datetime
    source: DataSourcePublic
    columns: list[DatasetColumn]
    sample_rows: list[dict[str, Any]]


class DatasetCreatedResponse(BaseModel):
    """Response from the upload endpoint. Matches :class:`DatasetSummary`
    plus the inferred columns so the frontend can navigate straight
    into the detail view without a second round-trip."""

    dataset: DatasetSummary
    columns: list[DatasetColumn]


# ---------------------------------------------------------------------------
# List response wrappers
# ---------------------------------------------------------------------------


class DatasetListResponse(BaseModel):
    datasets: list[DatasetSummary]


# ---------------------------------------------------------------------------
# Database sources (slice C — postgres; slice D extends to mssql)
# ---------------------------------------------------------------------------


class DatabaseConnectionConfig(_StrictModel):
    """User-supplied DB credentials. Slice C accepts only postgres.

    The frontend collects these in a form; we never echo the password
    back. The backend encrypts the dict and stores it in
    ``data_sources.connection_config_encrypted``.
    """

    kind: DataSourceKind  # only "postgres" honoured in slice C
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=255)
    user: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=0, max_length=500)
    sslmode: str = Field(default="prefer", max_length=32)


class ConnectionTestResponse(BaseModel):
    ok: bool
    error: str | None = None


class TableInfoPublic(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    estimated_rows: int | None

    model_config = ConfigDict(populate_by_name=True)


class TablesListResponse(BaseModel):
    tables: list[TableInfoPublic]


class ImportTableRequest(_StrictModel):
    """One row in the import payload. ``dataset_name`` defaults to
    ``{schema}.{table}`` if omitted."""

    schema_name: str = Field(min_length=1, max_length=255, alias="schema")
    table: str = Field(min_length=1, max_length=255)
    dataset_name: str | None = Field(default=None, max_length=160)

    model_config = ConfigDict(populate_by_name=True, extra="forbid", str_strip_whitespace=True)


class ImportTablesRequest(_StrictModel):
    tables: list[ImportTableRequest] = Field(min_length=1, max_length=50)


class ImportTablesResponse(BaseModel):
    datasets: list[DatasetSummary]


class DataSourceListResponse(BaseModel):
    sources: list[DataSourcePublic]


# ---------------------------------------------------------------------------
# Profiling (slice E)
# ---------------------------------------------------------------------------


class TopValue(BaseModel):
    value: str
    count: int


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float
    distinct_count: int | None
    min: str | None
    max: str | None
    top_values: list[TopValue] = Field(default_factory=list)


class DatasetProfile(BaseModel):
    id: UUID
    dataset_id: UUID
    status: str
    row_count: int | None
    columns: list[ColumnProfile] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None
    error: str | None


# ---------------------------------------------------------------------------
# Sharing (slice F)
# ---------------------------------------------------------------------------


class UpdateVisibilityRequest(_StrictModel):
    visibility: DatasetVisibility


class GrantUserRequest(_StrictModel):
    user_id: UUID


class DatasetGrantPublic(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    granted_at: datetime


class DatasetGrantsResponse(BaseModel):
    grants: list[DatasetGrantPublic]


class WorkspaceMember(BaseModel):
    user_id: UUID
    email: str
    role: str


class WorkspaceMembersResponse(BaseModel):
    members: list[WorkspaceMember]


__all__ = [
    "ColumnProfile",
    "ConnectionTestResponse",
    "DataSourceListResponse",
    "DataSourcePublic",
    "DatabaseConnectionConfig",
    "DatasetColumn",
    "DatasetCreatedResponse",
    "DatasetDetail",
    "DatasetGrantPublic",
    "DatasetGrantsResponse",
    "DatasetListResponse",
    "DatasetProfile",
    "DatasetSummary",
    "GrantUserRequest",
    "ImportTableRequest",
    "ImportTablesRequest",
    "ImportTablesResponse",
    "TableInfoPublic",
    "TablesListResponse",
    "TopValue",
    "UpdateVisibilityRequest",
    "WorkspaceMember",
    "WorkspaceMembersResponse",
]
