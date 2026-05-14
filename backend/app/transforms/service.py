"""Working-copy service.

Two responsibilities, kept narrow:

1. **Materialise** a working copy from a dataset on first use. Reads
   the source file via the existing :mod:`app.data.storage` helpers,
   writes a parquet snapshot under ``{tenant}/working_copies/{wc_id}/v0.parquet``,
   and records the row in ``dataset_working_copies``.

2. **Apply** an operation to a working copy: read the current snapshot,
   call :func:`app.transforms.dispatcher.apply_operation`, write the
   result to a new snapshot path, update the row, journal the change.

Read-only inspections short-circuit step 2: they don't write a new
snapshot, they just return the summary + visuals.

Commit policy: this module **flushes** so the router/service can
read back ids; the **caller** commits. Same convention as
:mod:`app.data.service`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import polars as pl
from sqlalchemy import select

from app.core import encryption
from app.data.models import Dataset, DataSource, DataSourceKind
from app.transforms.dispatcher import (
    OperationResult,
    apply_operation,
    is_mutating,
)
from app.transforms.models import DatasetOperation, DatasetWorkingCopy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.data.storage import LocalFileStorage


class WorkingCopyError(Exception):
    """Working-copy specific failure (missing dataset, can't read file, etc.)."""


# ---------------------------------------------------------------------------
# Snapshot path helpers
# ---------------------------------------------------------------------------


def _working_copy_dir(tenant_id: UUID, wc_id: UUID) -> str:
    return f"{tenant_id}/working_copies/{wc_id}"


def _snapshot_path(tenant_id: UUID, wc_id: UUID, label: str) -> str:
    """A fresh snapshot file for one operation. ``label`` is a short
    tag (``v0``, ``after_dedupe``) used for debuggability — the real
    uniqueness comes from a UUID4 suffix."""
    return f"{_working_copy_dir(tenant_id, wc_id)}/{label}_{uuid4().hex[:8]}.parquet"


# ---------------------------------------------------------------------------
# Materialising a working copy from the source dataset
# ---------------------------------------------------------------------------


def _read_source_frame(
    *,
    storage: LocalFileStorage,
    source: DataSource,
    dataset: Dataset,
) -> pl.DataFrame:
    """Best-effort load of the dataset into a polars DataFrame.

    For file-backed sources we use the stored path from the source's
    encrypted config. DB-backed sources fall out of scope for this
    first slice — the transform engine only operates on materialised
    data and we don't yet snapshot DB tables into parquet on a
    schedule. The agent gracefully tells the user via
    ``WorkingCopyError``.
    """
    if source.kind not in (
        DataSourceKind.csv,
        DataSourceKind.parquet,
        DataSourceKind.xlsx,
    ):
        raise WorkingCopyError(
            "Por ahora la ejecución solo funciona con datasets cargados desde archivo "
            "(CSV, Parquet, Excel). Los conectados a bases de datos llegan pronto."
        )
    raw = encryption.decrypt(source.connection_config_encrypted)
    config = json.loads(raw.decode())
    relative = config.get("path")
    if not isinstance(relative, str):
        raise WorkingCopyError("La configuración del dataset no apunta a un archivo válido.")
    abs_path = storage.absolute_path(relative)
    if source.kind is DataSourceKind.csv:
        return pl.read_csv(abs_path, infer_schema_length=10000)
    if source.kind is DataSourceKind.parquet:
        return pl.read_parquet(abs_path)
    # xlsx
    locator = dataset.locator or {}
    sheet = locator.get("sheet")
    return pl.read_excel(abs_path, sheet_name=sheet) if sheet else pl.read_excel(abs_path)


async def get_or_create_working_copy(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    dataset_id: UUID,
) -> DatasetWorkingCopy:
    """Look up the caller's working copy for the dataset; create one
    on first use by snapshotting the source into parquet."""
    existing = (
        await session.execute(
            select(DatasetWorkingCopy).where(
                DatasetWorkingCopy.dataset_id == dataset_id,
                DatasetWorkingCopy.created_by == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    row = (
        await session.execute(
            select(Dataset, DataSource)
            .join(DataSource, Dataset.source_id == DataSource.id)
            .where(Dataset.id == dataset_id)
        )
    ).one_or_none()
    if row is None:
        raise WorkingCopyError("No encontré ese dataset, o ya no tienes acceso a él.")
    dataset, source = row

    frame = _read_source_frame(storage=storage, source=source, dataset=dataset)
    wc_id = uuid4()
    snapshot_relative = _snapshot_path(tenant_id, wc_id, "v0")
    snapshot_abs = storage.absolute_path(snapshot_relative)
    snapshot_abs.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(snapshot_abs)

    wc = DatasetWorkingCopy(
        id=wc_id,
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        created_by=user_id,
        snapshot_path=snapshot_relative,
        row_count=frame.height,
        column_count=frame.width,
    )
    session.add(wc)
    await session.flush()
    return wc


def _read_snapshot(storage: LocalFileStorage, path: str) -> pl.DataFrame:
    return pl.read_parquet(storage.absolute_path(path))


# ---------------------------------------------------------------------------
# Running an operation
# ---------------------------------------------------------------------------


async def run_operation(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    working_copy: DatasetWorkingCopy,
    op: str,
    args: dict[str, Any],
    conversation_id: UUID | None = None,
    message_id: UUID | None = None,
) -> OperationResult:
    """Run one op against ``working_copy``.

    Mutating ops produce a new snapshot, advance the working copy
    pointer, and journal the change in ``dataset_operations``.
    Inspections short-circuit: they read, return the summary, and
    don't touch storage or the journal.
    """
    frame = _read_snapshot(storage, working_copy.snapshot_path)
    result = apply_operation(op, args, frame=frame)

    if is_mutating(op) and result.frame is not None:
        new_path = _snapshot_path(tenant_id, working_copy.id, op)
        abs_new = storage.absolute_path(new_path)
        abs_new.parent.mkdir(parents=True, exist_ok=True)
        result.frame.write_parquet(abs_new)
        before_path = working_copy.snapshot_path
        rows_before = working_copy.row_count
        working_copy.snapshot_path = new_path
        working_copy.row_count = result.frame.height
        working_copy.column_count = result.frame.width

        journal = DatasetOperation(
            tenant_id=tenant_id,
            working_copy_id=working_copy.id,
            created_by=user_id,
            op=op,
            args=args,
            snapshot_before_path=before_path,
            snapshot_after_path=new_path,
            rows_before=rows_before,
            rows_after=result.frame.height,
            conversation_id=conversation_id,
            message_id=message_id,
            result_summary=result.summary,
        )
        session.add(journal)
        await session.flush()

    return result


# ---------------------------------------------------------------------------
# Undo / reset
# ---------------------------------------------------------------------------


async def undo_operation(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    working_copy: DatasetWorkingCopy,
    operation_id: UUID,
) -> tuple[DatasetWorkingCopy, int]:
    """Roll the working copy back to the state *before* ``operation_id``.

    Every operation later than the target (and the target itself) gets
    its ``undone_at`` stamped. The working copy's ``snapshot_path``
    moves to the target operation's ``snapshot_before_path`` so the
    next read sees the pre-op state. Returns the updated working copy
    plus the count of operations marked undone.
    """
    op = (
        await session.execute(
            select(DatasetOperation).where(
                DatasetOperation.id == operation_id,
                DatasetOperation.working_copy_id == working_copy.id,
            )
        )
    ).scalar_one_or_none()
    if op is None:
        raise WorkingCopyError("No encontré esa operación en el historial.")
    if op.undone_at is not None:
        raise WorkingCopyError("Esa operación ya estaba deshecha.")

    # Mark this op + every later (still-active) op as undone. We
    # stamp from oldest to newest so the audit trail keeps a sensible
    # order even though they share the same timestamp.
    later = (
        (
            await session.execute(
                select(DatasetOperation)
                .where(
                    DatasetOperation.working_copy_id == working_copy.id,
                    DatasetOperation.created_at >= op.created_at,
                    DatasetOperation.undone_at.is_(None),
                )
                .order_by(DatasetOperation.created_at)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for entry in later:
        entry.undone_at = now

    # Restore the working copy pointer to the *before* snapshot of the
    # target operation. Re-read the parquet to refresh the row count.
    working_copy.snapshot_path = op.snapshot_before_path
    frame = _read_snapshot(storage, op.snapshot_before_path)
    working_copy.row_count = frame.height
    working_copy.column_count = frame.width
    await session.flush()
    return working_copy, len(later)


async def reset_working_copy(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    working_copy: DatasetWorkingCopy,
) -> tuple[DatasetWorkingCopy, int]:
    """Undo every operation, restoring the working copy to v0.

    Effectively a "rollback to the original CSV" for the user. The
    journal rows stay so we still have an audit trail of what was
    tried; they just all get ``undone_at`` stamped.
    """
    active = (
        (
            await session.execute(
                select(DatasetOperation)
                .where(
                    DatasetOperation.working_copy_id == working_copy.id,
                    DatasetOperation.undone_at.is_(None),
                )
                .order_by(DatasetOperation.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not active:
        return working_copy, 0
    # The earliest active op's ``snapshot_before_path`` is the v0
    # snapshot — every subsequent op chained off the previous one.
    v0_path = active[0].snapshot_before_path
    now = datetime.now(UTC)
    for entry in active:
        entry.undone_at = now
    working_copy.snapshot_path = v0_path
    frame = _read_snapshot(storage, v0_path)
    working_copy.row_count = frame.height
    working_copy.column_count = frame.width
    await session.flush()
    return working_copy, len(active)


__all__ = [
    "WorkingCopyError",
    "get_or_create_working_copy",
    "reset_working_copy",
    "run_operation",
    "undo_operation",
]
