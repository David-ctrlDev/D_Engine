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


__all__ = [
    "DataSourcePublic",
    "DatasetColumn",
    "DatasetCreatedResponse",
    "DatasetDetail",
    "DatasetListResponse",
    "DatasetSummary",
]
