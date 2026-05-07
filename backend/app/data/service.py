"""Data-domain service layer.

The router is a thin shell — all business logic lives here so the
same operations are reachable from a future background worker (the
profiler) or from tests without spinning up FastAPI.

Boundaries
----------

Every public function takes the *DB session* and returns Python
domain objects (SQLAlchemy rows or plain dataclasses). The session
arrives with RLS GUCs already set by the router's
``get_authenticated_session`` dependency, so policies do the heavy
lifting on visibility — the service trusts the DB.

Commit ownership: the **router** commits. The service only flushes
so we can read back generated PKs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

import polars as pl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import encryption
from app.data.errors import (
    DatasetNotFoundError,
    DuplicateNameError,
    InvalidFileError,
)
from app.data.models import (
    Dataset,
    DatasetKind,
    DatasetVisibility,
    DataSource,
    DataSourceKind,
)
from app.data.parsers.common import InferredSchema
from app.data.parsers.csv_parser import infer_csv
from app.data.storage import LocalFileStorage, StoredFile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Sample rows we re-read on the detail endpoint. Capped so the
# response can't blow up on wide datasets.
_DETAIL_SAMPLE_ROWS = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encrypt_file_config(stored: StoredFile) -> bytes:
    """Encrypt the {path, sha256, size, original_filename} blob.

    The encrypted column is shaped the same as for DB sources so the
    runtime never branches on ``kind`` to decide whether to decrypt.
    """
    payload = json.dumps(
        {
            "path": stored.path,
            "sha256": stored.sha256,
            "size_bytes": stored.size_bytes,
            "original_filename": stored.original_filename,
        },
        sort_keys=True,
    ).encode()
    return encryption.encrypt(payload)


def _kind_from_filename(name: str) -> DataSourceKind:
    lower = name.lower()
    if lower.endswith(".csv"):
        return DataSourceKind.csv
    if lower.endswith(".parquet"):
        return DataSourceKind.parquet
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return DataSourceKind.xlsx
    raise InvalidFileError(f"unsupported file extension: {name!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_dataset_from_upload(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    stored: StoredFile,
    dataset_name: str,
) -> tuple[DataSource, Dataset, InferredSchema]:
    """Persist an uploaded file as a (source, dataset) pair.

    The file has *already* been written to disk before we get here —
    storage I/O happens in the router so a ``FileTooLargeError`` is
    raised before we touch the DB. The service:

    1. infers the schema (CSV-only in slice A, dispatches by kind),
    2. inserts the source + dataset rows,
    3. lets the caller commit.

    On a unique-constraint violation we re-raise as
    :class:`DuplicateNameError` so the router maps it to 409.
    """
    kind = _kind_from_filename(stored.original_filename)

    # Schema inference — disk read, no DB.
    if kind is DataSourceKind.csv:
        try:
            inferred = infer_csv(storage.absolute_path(stored.path))
        except Exception as e:
            raise InvalidFileError(f"could not parse CSV: {e}") from e
    else:  # pragma: no cover — slice B/C add the others
        raise InvalidFileError(f"slice A only supports CSV uploads, got {kind}")

    source = DataSource(
        tenant_id=tenant_id,
        created_by=user_id,
        name=stored.original_filename,
        kind=kind,
        connection_config_encrypted=_encrypt_file_config(stored),
    )
    session.add(source)

    try:
        # Flush the source so we have its PK for the dataset FK.
        await session.flush()
    except IntegrityError as e:
        # ``uq_data_sources_tenant_id_name`` — same filename twice.
        await session.rollback()
        raise DuplicateNameError(stored.original_filename) from e

    dataset = Dataset(
        tenant_id=tenant_id,
        source_id=source.id,
        created_by=user_id,
        name=dataset_name,
        kind=DatasetKind.file_sheet,
        locator={
            "path": stored.path,
            "original_filename": stored.original_filename,
        },
        inferred_schema=inferred.to_jsonb(),
        row_count_estimate=inferred.row_count_estimate,
        visibility=DatasetVisibility.private,
    )
    session.add(dataset)

    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise DuplicateNameError(dataset_name) from e

    return source, dataset, inferred


async def list_datasets(
    session: AsyncSession,
) -> list[tuple[Dataset, DataSource]]:
    """Every dataset visible to the current user (RLS filters).

    Joins through to the parent source so the list endpoint can
    render the source kind without a second round-trip.
    """
    stmt = (
        select(Dataset, DataSource)
        .join(DataSource, Dataset.source_id == DataSource.id)
        .order_by(Dataset.created_at.desc())
    )
    result = await session.execute(stmt)
    return [(d, s) for d, s in result.all()]


async def get_dataset_detail(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    dataset_id: UUID,
) -> tuple[Dataset, DataSource, list[dict[str, object]]]:
    """Fetch a dataset + its source + a fresh sample.

    The sample is *not* persisted — we re-read it from disk so the
    detail view stays in sync with the underlying file even if the
    user replaces it later. Cheap because polars caps the read at
    :data:`_DETAIL_SAMPLE_ROWS`.
    """
    stmt = (
        select(Dataset, DataSource)
        .join(DataSource, Dataset.source_id == DataSource.id)
        .where(Dataset.id == dataset_id)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise DatasetNotFoundError(str(dataset_id))
    dataset, source = row

    sample_rows: list[dict[str, object]] = []
    if source.kind is DataSourceKind.csv:
        path = storage.absolute_path(str(dataset.locator["path"]))
        try:
            sample_df = pl.read_csv(path, n_rows=_DETAIL_SAMPLE_ROWS)
            sample_rows = sample_df.to_dicts()
        except Exception:
            sample_rows = []

    return dataset, source, sample_rows


__all__ = [
    "create_dataset_from_upload",
    "get_dataset_detail",
    "list_datasets",
]
