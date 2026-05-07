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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import polars as pl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import encryption
from app.data.errors import (
    DatasetNotFoundError,
    DuplicateNameError,
    InvalidFileError,
    UnsupportedSourceKindError,
)
from app.data.models import (
    Dataset,
    DatasetKind,
    DatasetVisibility,
    DataSource,
    DataSourceKind,
    ProfileRun,
    ProfileRunStatus,
)
from app.data.parsers.common import InferredSchema
from app.data.parsers.csv_parser import infer_csv
from app.data.parsers.parquet_parser import infer_parquet
from app.data.parsers.xlsx_parser import infer_xlsx
from app.data.probes import ProbeResult, TableInfo
from app.data.probes import postgres as pg_probe
from app.data.probes.mssql import mssql as mssql_probe
from app.data.probes.mssql import mssql_azure as mssql_azure_probe
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
    abs_path = storage.absolute_path(stored.path)

    # Dispatch by kind. Each parser raises on malformed files; we
    # wrap into InvalidFileError so the router maps to 422 cleanly.
    locator_extra: dict[str, Any] = {}
    try:
        if kind is DataSourceKind.csv:
            inferred = infer_csv(abs_path)
        elif kind is DataSourceKind.parquet:
            inferred = infer_parquet(abs_path)
        elif kind is DataSourceKind.xlsx:
            inferred, sheet = infer_xlsx(abs_path)
            locator_extra["sheet"] = sheet
        else:  # pragma: no cover — DB kinds don't go through this path
            raise InvalidFileError(f"unsupported file kind: {kind}")
    except InvalidFileError:
        raise
    except Exception as e:
        raise InvalidFileError(f"could not parse {kind.value}: {e}") from e

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
            **locator_extra,
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
    locator = dataset.locator or {}
    if source.kind in (DataSourceKind.csv, DataSourceKind.parquet, DataSourceKind.xlsx):
        path = storage.absolute_path(str(locator.get("path", "")))
        try:
            if source.kind is DataSourceKind.csv:
                sample_df = pl.read_csv(path, n_rows=_DETAIL_SAMPLE_ROWS)
            elif source.kind is DataSourceKind.parquet:
                sample_df = pl.read_parquet(path, n_rows=_DETAIL_SAMPLE_ROWS)
            else:  # xlsx
                sheet = str(locator.get("sheet", "Sheet1"))
                sample_df = pl.read_excel(path, sheet_name=sheet).head(_DETAIL_SAMPLE_ROWS)
            sample_rows = sample_df.to_dicts()
        except Exception:
            sample_rows = []

    return dataset, source, sample_rows


# ---------------------------------------------------------------------------
# Database sources (slice C: postgres only — slice D extends to mssql)
# ---------------------------------------------------------------------------


def _encrypt_db_config(config: dict[str, Any]) -> bytes:
    """Encrypt the connection_config dict for a DB source.

    Same shape as :func:`_encrypt_file_config` so callers don't
    branch on kind when persisting. ``json.dumps`` with
    ``sort_keys=True`` makes the ciphertext stable for tests.
    """
    payload = json.dumps(config, sort_keys=True).encode()
    return encryption.encrypt(payload)


def _decrypt_db_config(blob: bytes) -> dict[str, Any]:
    raw = encryption.decrypt(blob)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("encrypted config is not a dict")
    return parsed


def _probe_for(kind: DataSourceKind) -> Any:
    """Pick the right probe module for a given kind. Slice D adds mssql.

    Returns ``Any`` because we don't have a Protocol for "module-shaped
    probe object" — each probe is a module (not a class), and mypy
    doesn't have a way to express "module that exposes these three
    coroutines". The caller is the only consumer; types are recovered
    at the await sites."""
    if kind is DataSourceKind.postgres:
        return pg_probe
    if kind is DataSourceKind.mssql:
        return mssql_probe
    if kind is DataSourceKind.mssql_azure:
        return mssql_azure_probe
    raise UnsupportedSourceKindError(f"DB kind not supported yet: {kind}")


async def test_database_connection(*, kind: DataSourceKind, config: dict[str, Any]) -> ProbeResult:
    """Wrap the kind-specific probe so the router doesn't need to know
    about the dispatch."""
    probe = _probe_for(kind)
    result: ProbeResult = await probe.test_connection(config)
    return result


async def create_database_source(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    kind: DataSourceKind,
    name: str,
    config: dict[str, Any],
) -> DataSource:
    """Persist a database source. Caller has already run the probe;
    we just store the encrypted config and stamp the test result."""
    source = DataSource(
        tenant_id=tenant_id,
        created_by=user_id,
        name=name,
        kind=kind,
        connection_config_encrypted=_encrypt_db_config(config),
        last_tested_at=datetime.now(UTC),
        last_test_status="ok",
        last_test_error=None,
    )
    session.add(source)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise DuplicateNameError(name) from e
    return source


async def list_sources(session: AsyncSession) -> list[DataSource]:
    stmt = select(DataSource).order_by(DataSource.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_source_tables(session: AsyncSession, *, source_id: UUID) -> list[TableInfo]:
    """List user-visible tables on a DB source. RLS makes the source
    invisible if the caller doesn't own it, so a 404 here means the
    source is gone or hidden — not a permission bug."""
    stmt = select(DataSource).where(DataSource.id == source_id)
    result = await session.execute(stmt)
    source = result.scalar_one_or_none()
    if source is None:
        raise DatasetNotFoundError(str(source_id))
    config = _decrypt_db_config(source.connection_config_encrypted)
    probe = _probe_for(source.kind)
    tables: list[TableInfo] = await probe.list_tables(config)
    return tables


async def import_tables_as_datasets(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    source_id: UUID,
    requests: list[tuple[str, str, str | None]],
) -> list[tuple[Dataset, DataSource]]:
    """Import each (schema, table, dataset_name) as a Dataset row.

    The introspection happens once per table — column types come back
    in :class:`InferredSchema` and land in ``Dataset.inferred_schema``.
    The whole import is one transaction: any duplicate name causes a
    rollback so the user sees an all-or-nothing result.
    """
    stmt = select(DataSource).where(DataSource.id == source_id)
    result = await session.execute(stmt)
    source = result.scalar_one_or_none()
    if source is None:
        raise DatasetNotFoundError(str(source_id))

    config = _decrypt_db_config(source.connection_config_encrypted)
    probe = _probe_for(source.kind)

    created: list[tuple[Dataset, DataSource]] = []
    for schema_name, table_name, requested_name in requests:
        inferred = await probe.introspect_table(config, schema_name, table_name)
        dataset_name = requested_name or f"{schema_name}.{table_name}"
        dataset = Dataset(
            tenant_id=tenant_id,
            source_id=source.id,
            created_by=user_id,
            name=dataset_name,
            kind=DatasetKind.table,
            locator={"schema": schema_name, "table": table_name},
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
        created.append((dataset, source))
    return created


# ---------------------------------------------------------------------------
# Profiling (slice E)
# ---------------------------------------------------------------------------


async def run_profile(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    dataset_id: UUID,
) -> ProfileRun:
    """Run a profile against a dataset and persist the result.

    The whole thing happens inline — no background worker yet, so the
    HTTP request waits. For files this is fine up to a few hundred MB;
    for huge DB tables we already cap at the sample size in
    :mod:`app.data.profiling`.
    """
    from app.data.profiling import profile_db_dataset, profile_file_dataset

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

    # Insert the row in ``running`` state so the user can poll if we
    # ever move this off the request thread.
    profile_run = ProfileRun(
        tenant_id=tenant_id,
        dataset_id=dataset.id,
        created_by=user_id,
        status=ProfileRunStatus.running,
    )
    session.add(profile_run)
    await session.flush()
    # The profile run row is committed up-front so a crash mid-run
    # leaves a visible ``running`` row instead of nothing.
    await session.commit()

    try:
        if source.kind in (
            DataSourceKind.csv,
            DataSourceKind.parquet,
            DataSourceKind.xlsx,
        ):
            result_payload = await profile_file_dataset(
                kind=source.kind,
                locator=dataset.locator or {},
                abs_resolver=storage.absolute_path,
            )
        else:
            config = _decrypt_db_config(source.connection_config_encrypted)
            probe = _probe_for(source.kind)
            locator = dataset.locator or {}
            schema = str(locator.get("schema", ""))
            table = str(locator.get("table", ""))
            result_payload = await profile_db_dataset(
                probe=probe,
                config=config,
                schema=schema,
                table=table,
            )
    except Exception as e:
        profile_run.status = ProfileRunStatus.failed
        profile_run.error = str(e)[:1000]
        profile_run.completed_at = datetime.now(UTC)
        await session.commit()
        return profile_run

    profile_run.status = ProfileRunStatus.completed
    profile_run.result = result_payload
    profile_run.completed_at = datetime.now(UTC)
    # Stamp the row count back on the dataset so the list view shows it.
    rc = result_payload.get("row_count")
    if isinstance(rc, int) and rc >= 0:
        dataset.row_count_estimate = rc
    await session.commit()
    return profile_run


async def get_latest_profile(session: AsyncSession, *, dataset_id: UUID) -> ProfileRun | None:
    stmt = (
        select(ProfileRun)
        .where(ProfileRun.dataset_id == dataset_id)
        .order_by(ProfileRun.started_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


__all__ = [
    "create_database_source",
    "create_dataset_from_upload",
    "get_dataset_detail",
    "get_latest_profile",
    "import_tables_as_datasets",
    "list_datasets",
    "list_source_tables",
    "list_sources",
    "run_profile",
    "test_database_connection",
]
