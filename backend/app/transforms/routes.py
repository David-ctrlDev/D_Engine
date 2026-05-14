"""HTTP layer for the working-copy / transformation engine.

Endpoints
---------

* ``GET /api/v1/datasets/{id}/working-copy`` — the user's current
  working-copy state (row/column counts, latest snapshot path, recent
  operations). When no working copy exists yet, returns a 404 — the
  agent will create one on first tool call.

* ``GET /api/v1/datasets/{id}/working-copy/sample`` — a sample of the
  current data (rows + columns). The "see the cleaned data" surface
  the chat links to.

* ``GET /api/v1/datasets/{id}/working-copy/operations`` — the journal:
  every transform that ran, in order, with rows-before/after counts
  and the conversation that triggered it. Powers the future "undo"
  button.

Visibility is delegated to RLS — the working copy is private to its
creator (the workspace owner sees everything as a governance override,
same model as datasets / conversations).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import polars as pl
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select

from app.auth.dependencies import AuthSessionDep, CurrentUserDep
from app.data.deps import StorageDep
from app.transforms import service as transforms_service
from app.transforms.models import DatasetOperation, DatasetWorkingCopy

router = APIRouter(prefix="/api/v1/datasets", tags=["working-copy"])


# How many rows of the sample we ship back. Capped so the response
# stays small for big datasets.
_SAMPLE_ROWS = 25


def _parse_uuid_or_404(raw: str, label: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} no encontrado."
        ) from e


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------


class WorkingCopySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    snapshot_path: str
    row_count: int | None
    column_count: int | None
    created_at: datetime
    updated_at: datetime


class WorkingCopySampleResponse(BaseModel):
    working_copy_id: UUID
    columns: list[dict[str, str]]
    rows: list[dict[str, Any]]
    row_count: int
    column_count: int


class WorkingCopyOperationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    op: str
    args: dict[str, Any]
    rows_before: int | None
    rows_after: int | None
    result_summary: dict[str, Any] | None
    conversation_id: UUID | None
    message_id: UUID | None
    created_at: datetime
    undone_at: datetime | None


class WorkingCopyOperationsResponse(BaseModel):
    operations: list[WorkingCopyOperationPublic]


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


async def _find_working_copy_for_user(
    session: AuthSessionDep, dataset_id: UUID, user_id: UUID
) -> DatasetWorkingCopy:
    wc = (
        await session.execute(
            select(DatasetWorkingCopy).where(
                DatasetWorkingCopy.dataset_id == dataset_id,
                DatasetWorkingCopy.created_by == user_id,
            )
        )
    ).scalar_one_or_none()
    if wc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Todavía no hay una versión limpia de este dataset. "
                "Hablale al agente para que empiece a trabajar con tus datos."
            ),
        )
    return wc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{dataset_id}/working-copy", response_model=WorkingCopySummary)
async def get_working_copy(
    dataset_id: str, session: AuthSessionDep, user: CurrentUserDep
) -> WorkingCopySummary:
    did = _parse_uuid_or_404(dataset_id, "Dataset")
    wc = await _find_working_copy_for_user(session, did, user.id)
    return WorkingCopySummary.model_validate(wc)


@router.get(
    "/{dataset_id}/working-copy/sample", response_model=WorkingCopySampleResponse
)
async def get_working_copy_sample(
    dataset_id: str,
    session: AuthSessionDep,
    user: CurrentUserDep,
    storage: StorageDep,
) -> WorkingCopySampleResponse:
    """Sample rows + schema of the current snapshot.

    Reads the parquet file the working-copy row points at and returns
    the first ``_SAMPLE_ROWS`` rows plus the full column list. The
    frontend renders this as a table inside a "Datos limpios (versión
    actual)" panel.
    """
    did = _parse_uuid_or_404(dataset_id, "Dataset")
    wc = await _find_working_copy_for_user(session, did, user.id)

    abs_path = storage.absolute_path(wc.snapshot_path)
    if not abs_path.is_file():  # pragma: no cover - storage drift
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="El archivo de la versión actual no está disponible.",
        )
    frame = pl.read_parquet(abs_path)
    sample = frame.head(_SAMPLE_ROWS)
    rows: list[dict[str, Any]] = []
    for r in sample.iter_rows(named=True):
        rows.append({k: _jsonable(v) for k, v in r.items()})
    cols = [{"name": c, "dtype": str(frame.schema[c])} for c in frame.columns]
    return WorkingCopySampleResponse(
        working_copy_id=wc.id,
        columns=cols,
        rows=rows,
        row_count=frame.height,
        column_count=frame.width,
    )


@router.get(
    "/{dataset_id}/working-copy/operations",
    response_model=WorkingCopyOperationsResponse,
)
async def list_working_copy_operations(
    dataset_id: str, session: AuthSessionDep, user: CurrentUserDep
) -> WorkingCopyOperationsResponse:
    did = _parse_uuid_or_404(dataset_id, "Dataset")
    wc = await _find_working_copy_for_user(session, did, user.id)
    rows = (
        (
            await session.execute(
                select(DatasetOperation)
                .where(DatasetOperation.working_copy_id == wc.id)
                .order_by(desc(DatasetOperation.created_at))
            )
        )
        .scalars()
        .all()
    )
    return WorkingCopyOperationsResponse(
        operations=[WorkingCopyOperationPublic.model_validate(r) for r in rows]
    )


# ---------------------------------------------------------------------------
# Undo / reset
# ---------------------------------------------------------------------------


class UndoResponse(BaseModel):
    """What the UI gets back after an undo/reset call.

    ``working_copy`` is the post-rollback state; ``undone_count`` is
    how many operations were affected (1 for a single-step undo, N
    for "undo from step K onwards", everything-still-active for a
    full reset)."""

    working_copy: WorkingCopySummary
    undone_count: int


@router.post(
    "/{dataset_id}/working-copy/operations/{operation_id}/undo",
    response_model=UndoResponse,
)
async def undo_working_copy_operation(
    dataset_id: str,
    operation_id: str,
    session: AuthSessionDep,
    user: CurrentUserDep,
    storage: StorageDep,
) -> UndoResponse:
    """Roll the working copy back to the state right *before* this
    operation. Every later operation is also marked undone — you
    can't keep step 3 if you rolled back step 2."""
    did = _parse_uuid_or_404(dataset_id, "Dataset")
    oid = _parse_uuid_or_404(operation_id, "Operación")
    wc = await _find_working_copy_for_user(session, did, user.id)
    try:
        updated, count = await transforms_service.undo_operation(
            session,
            storage=storage,
            working_copy=wc,
            operation_id=oid,
        )
    except transforms_service.WorkingCopyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    await session.commit()
    return UndoResponse(
        working_copy=WorkingCopySummary.model_validate(updated),
        undone_count=count,
    )


@router.post(
    "/{dataset_id}/working-copy/reset",
    response_model=UndoResponse,
)
async def reset_working_copy(
    dataset_id: str,
    session: AuthSessionDep,
    user: CurrentUserDep,
    storage: StorageDep,
) -> UndoResponse:
    """Discard every transformation, restoring the working copy to
    the original CSV. Journal rows stay (with ``undone_at`` stamped)
    for the audit trail."""
    did = _parse_uuid_or_404(dataset_id, "Dataset")
    wc = await _find_working_copy_for_user(session, did, user.id)
    updated, count = await transforms_service.reset_working_copy(
        session, storage=storage, working_copy=wc
    )
    await session.commit()
    return UndoResponse(
        working_copy=WorkingCopySummary.model_validate(updated),
        undone_count=count,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _jsonable(v: Any) -> Any:
    """Make polars cell values safe for JSON.

    Datetimes / dates → ISO strings; bytes → repr; nan → None. Everything
    else passes through.
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bytes):
        return repr(v)
    if isinstance(v, float) and v != v:  # NaN check
        return None
    return v


__all__ = ["router"]
