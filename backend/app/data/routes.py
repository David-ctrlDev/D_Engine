"""HTTP layer for /api/v1/sources and /api/v1/datasets.

Slice A surface
---------------

* ``POST   /api/v1/sources/upload``  — multipart upload (csv only),
  creates a ``DataSource`` + the matching ``Dataset`` in one shot.
* ``GET    /api/v1/datasets``        — list datasets visible to the
  caller (RLS filters automatically).
* ``GET    /api/v1/datasets/{id}``   — detail with inferred schema +
  fresh sample rows.

Adding parquet/xlsx (slice B) and DB sources (slice C) extends this
file in place — the upload endpoint already accepts a kind discriminator
through the file extension, and the DB-source endpoints will live next
to ``/sources/upload``.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.auth.dependencies import AccessClaimsDep, AuthSessionDep, CurrentUserDep
from app.data import service
from app.data.deps import StorageDep
from app.data.errors import (
    DatasetNotFoundError,
    DuplicateNameError,
    InvalidFileError,
    UnsupportedSourceKindError,
)
from app.data.schemas import (
    DatasetColumn,
    DatasetCreatedResponse,
    DatasetDetail,
    DatasetListResponse,
    DatasetSummary,
    DataSourcePublic,
)
from app.data.storage import FileTooLargeError, StorageError

sources_router = APIRouter(prefix="/api/v1/sources", tags=["sources"])
datasets_router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def _map_data_error(e: Exception) -> HTTPException:
    """Translate domain errors into HTTP statuses. Anything we don't
    recognise propagates and FastAPI returns 500 — that's the right
    behaviour for genuine bugs."""
    if isinstance(e, DuplicateNameError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A dataset named {e!s} already exists in this workspace.",
        )
    if isinstance(e, InvalidFileError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    if isinstance(e, UnsupportedSourceKindError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if isinstance(e, DatasetNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )
    if isinstance(e, FileTooLargeError):
        return HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    if isinstance(e, StorageError):  # pragma: no cover — disk-side bug
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage failed.",
        )
    raise e  # let it bubble


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


def _to_summary(dataset, source) -> DatasetSummary:  # type: ignore[no-untyped-def]
    return DatasetSummary(
        id=dataset.id,
        name=dataset.name,
        kind=dataset.kind,
        visibility=dataset.visibility,
        row_count_estimate=dataset.row_count_estimate,
        created_at=dataset.created_at,
        source_id=source.id,
        source_name=source.name,
        source_kind=source.kind,
    )


def _columns_from_jsonb(blob: dict[str, object] | None) -> list[DatasetColumn]:
    if not blob:
        return []
    columns_raw = blob.get("columns") or []
    out: list[DatasetColumn] = []
    if isinstance(columns_raw, list):
        for c in columns_raw:
            if isinstance(c, dict):
                out.append(
                    DatasetColumn(
                        name=str(c.get("name", "")),
                        dtype=str(c.get("dtype", "")),
                        nullable=bool(c.get("nullable", True)),
                        sample_values=[str(v) for v in (c.get("sample_values") or [])],
                    )
                )
    return out


# ---------------------------------------------------------------------------
# /sources/upload
# ---------------------------------------------------------------------------


@sources_router.post(
    "/upload",
    response_model=DatasetCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    storage: StorageDep,
    file: UploadFile = File(...),
    dataset_name: str = Form(..., min_length=1, max_length=160),
) -> DatasetCreatedResponse:
    """Upload a file (csv in slice A) and create the matching dataset.

    The file is streamed straight to disk by :class:`LocalFileStorage`
    in 1 MiB chunks; we never load the whole upload into memory.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="filename is required",
        )

    try:
        stored = storage.save(
            tenant_id=claims.tenant_id,
            original_filename=file.filename,
            stream=file.file,
        )
    except FileTooLargeError as e:
        raise _map_data_error(e) from e
    except StorageError as e:  # pragma: no cover
        raise _map_data_error(e) from e

    try:
        source, dataset, inferred = await service.create_dataset_from_upload(
            session,
            storage=storage,
            tenant_id=claims.tenant_id,
            user_id=user.id,
            stored=stored,
            dataset_name=dataset_name,
        )
    except (DuplicateNameError, InvalidFileError, UnsupportedSourceKindError) as e:
        # Compensate the file write — the DB row didn't land.
        storage.delete(stored.path)
        raise _map_data_error(e) from e

    await session.commit()

    summary = _to_summary(dataset, source)
    return DatasetCreatedResponse(
        dataset=summary,
        columns=[
            DatasetColumn(
                name=c.name,
                dtype=c.dtype,
                nullable=c.nullable,
                sample_values=c.sample_values,
            )
            for c in inferred.columns
        ],
    )


# ---------------------------------------------------------------------------
# /datasets
# ---------------------------------------------------------------------------


@datasets_router.get("", response_model=DatasetListResponse)
async def list_datasets(session: AuthSessionDep) -> DatasetListResponse:
    pairs = await service.list_datasets(session)
    return DatasetListResponse(datasets=[_to_summary(d, s) for d, s in pairs])


@datasets_router.get("/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(
    dataset_id: str,
    session: AuthSessionDep,
    storage: StorageDep,
) -> DatasetDetail:
    from uuid import UUID as _UUID

    try:
        did = _UUID(dataset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        ) from e

    try:
        dataset, source, sample_rows = await service.get_dataset_detail(
            session, storage=storage, dataset_id=did
        )
    except DatasetNotFoundError as e:
        raise _map_data_error(e) from e

    return DatasetDetail(
        id=dataset.id,
        name=dataset.name,
        kind=dataset.kind,
        visibility=dataset.visibility,
        row_count_estimate=dataset.row_count_estimate,
        created_at=dataset.created_at,
        source=DataSourcePublic.model_validate(source),
        columns=_columns_from_jsonb(dataset.inferred_schema),
        sample_rows=sample_rows,
    )


__all__ = ["datasets_router", "sources_router"]
