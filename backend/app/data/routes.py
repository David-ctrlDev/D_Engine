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
from app.data.models import DataSourceKind, ProfileRun
from app.data.schemas import (
    ColumnProfile,
    ConnectionTestResponse,
    DatabaseConnectionConfig,
    DatasetColumn,
    DatasetCreatedResponse,
    DatasetDetail,
    DatasetGrantPublic,
    DatasetGrantsResponse,
    DatasetListResponse,
    DatasetProfile,
    DatasetSummary,
    DataSourceListResponse,
    DataSourcePublic,
    GrantUserRequest,
    ImportTablesRequest,
    ImportTablesResponse,
    TableInfoPublic,
    TablesListResponse,
    TopValue,
    UpdateVisibilityRequest,
    WorkspaceMember,
    WorkspaceMembersResponse,
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


# ---------------------------------------------------------------------------
# /sources — database (postgres) sources
# ---------------------------------------------------------------------------


@sources_router.get("", response_model=DataSourceListResponse)
async def list_sources_endpoint(session: AuthSessionDep) -> DataSourceListResponse:
    sources = await service.list_sources(session)
    return DataSourceListResponse(sources=[DataSourcePublic.model_validate(s) for s in sources])


@sources_router.post(
    "/database",
    response_model=DataSourcePublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_database_source(
    body: DatabaseConnectionConfig,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> DataSourcePublic:
    """Create a DB source. We probe BEFORE persisting so a typo'd
    DSN gets a 400 instead of leaving a dead row in the DB.

    Slice C/D honours ``postgres``, ``mssql`` and ``mssql_azure``.
    File kinds (csv/parquet/xlsx) go through ``/sources/upload``.
    """
    if body.kind not in (
        DataSourceKind.postgres,
        DataSourceKind.mssql,
        DataSourceKind.mssql_azure,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Use /sources/upload for file kinds: {body.kind}",
        )

    config = {
        "host": body.host,
        "port": body.port,
        "database": body.database,
        "user": body.user,
        "password": body.password,
        "sslmode": body.sslmode,
    }
    probe = await service.test_database_connection(kind=body.kind, config=config)
    if not probe.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=probe.error or "Connection failed.",
        )

    try:
        source = await service.create_database_source(
            session,
            tenant_id=claims.tenant_id,
            user_id=user.id,
            kind=body.kind,
            name=body.name,
            config=config,
        )
    except DuplicateNameError as e:
        raise _map_data_error(e) from e

    await session.commit()
    return DataSourcePublic.model_validate(source)


@sources_router.post("/test", response_model=ConnectionTestResponse)
async def test_connection_endpoint(
    body: DatabaseConnectionConfig,
    _: CurrentUserDep,  # auth gate, no DB writes
) -> ConnectionTestResponse:
    """Run a probe without persisting. The frontend uses this for the
    'Test connection' button next to the form."""
    if body.kind not in (
        DataSourceKind.postgres,
        DataSourceKind.mssql,
        DataSourceKind.mssql_azure,
    ):
        return ConnectionTestResponse(
            ok=False, error=f"Use /sources/upload for file kinds: {body.kind}"
        )
    config = {
        "host": body.host,
        "port": body.port,
        "database": body.database,
        "user": body.user,
        "password": body.password,
        "sslmode": body.sslmode,
    }
    result = await service.test_database_connection(kind=body.kind, config=config)
    return ConnectionTestResponse(ok=result.ok, error=result.error)


@sources_router.get("/{source_id}/tables", response_model=TablesListResponse)
async def list_source_tables_endpoint(
    source_id: str,
    session: AuthSessionDep,
) -> TablesListResponse:
    from uuid import UUID as _UUID

    try:
        sid = _UUID(source_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found."
        ) from e
    try:
        tables = await service.list_source_tables(session, source_id=sid)
    except DatasetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found."
        ) from e
    except UnsupportedSourceKindError as e:
        raise _map_data_error(e) from e
    return TablesListResponse(
        tables=[
            TableInfoPublic(
                schema_name=t.schema,
                name=t.name,
                estimated_rows=t.estimated_rows,
            )
            for t in tables
        ]
    )


@sources_router.post(
    "/{source_id}/import",
    response_model=ImportTablesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_tables_endpoint(
    source_id: str,
    body: ImportTablesRequest,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> ImportTablesResponse:
    from uuid import UUID as _UUID

    try:
        sid = _UUID(source_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found."
        ) from e
    requests = [(t.schema_name, t.table, t.dataset_name) for t in body.tables]
    try:
        created = await service.import_tables_as_datasets(
            session,
            tenant_id=claims.tenant_id,
            user_id=user.id,
            source_id=sid,
            requests=requests,
        )
    except DatasetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found."
        ) from e
    except (DuplicateNameError, UnsupportedSourceKindError) as e:
        raise _map_data_error(e) from e

    await session.commit()
    return ImportTablesResponse(datasets=[_to_summary(d, s) for d, s in created])


# ---------------------------------------------------------------------------
# Profiling (slice E)
# ---------------------------------------------------------------------------


def _profile_to_response(run: ProfileRun) -> DatasetProfile:
    """Map a ProfileRun row to the API response. ``run.result`` is
    a JSONB blob; we surface the columns + row count and ignore the
    internal-only fields."""
    payload = run.result or {}
    columns_raw = payload.get("columns") if isinstance(payload, dict) else []
    columns: list[ColumnProfile] = []
    if isinstance(columns_raw, list):
        for c in columns_raw:
            if not isinstance(c, dict):
                continue
            top = c.get("top_values") or []
            top_models: list[TopValue] = []
            if isinstance(top, list):
                for tv in top:
                    if isinstance(tv, dict):
                        top_models.append(
                            TopValue(value=str(tv.get("value", "")), count=int(tv.get("count", 0)))
                        )
            columns.append(
                ColumnProfile(
                    name=str(c.get("name", "")),
                    dtype=str(c.get("dtype", "")),
                    null_count=int(c.get("null_count", 0)),
                    null_pct=float(c.get("null_pct", 0.0)),
                    distinct_count=(
                        int(c["distinct_count"]) if c.get("distinct_count") is not None else None
                    ),
                    min=c.get("min"),
                    max=c.get("max"),
                    top_values=top_models,
                )
            )
    return DatasetProfile(
        id=run.id,
        dataset_id=run.dataset_id,
        status=str(run.status.value),
        row_count=(
            int(payload["row_count"])
            if isinstance(payload, dict) and isinstance(payload.get("row_count"), int)
            else None
        ),
        columns=columns,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error=run.error,
    )


@datasets_router.post(
    "/{dataset_id}/profile",
    response_model=DatasetProfile,
    status_code=status.HTTP_201_CREATED,
)
async def run_profile_endpoint(
    dataset_id: str,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    storage: StorageDep,
) -> DatasetProfile:
    from uuid import UUID as _UUID

    try:
        did = _UUID(dataset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found."
        ) from e
    try:
        run = await service.run_profile(
            session,
            storage=storage,
            tenant_id=claims.tenant_id,
            user_id=user.id,
            dataset_id=did,
        )
    except DatasetNotFoundError as e:
        raise _map_data_error(e) from e
    return _profile_to_response(run)


@datasets_router.get("/{dataset_id}/profile", response_model=DatasetProfile)
async def get_profile_endpoint(dataset_id: str, session: AuthSessionDep) -> DatasetProfile:
    from uuid import UUID as _UUID

    try:
        did = _UUID(dataset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found."
        ) from e
    run = await service.get_latest_profile(session, dataset_id=did)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile yet.")
    return _profile_to_response(run)


# ---------------------------------------------------------------------------
# Sharing — visibility + grants (slice F)
# ---------------------------------------------------------------------------


@datasets_router.patch("/{dataset_id}", response_model=DatasetSummary)
async def update_dataset_visibility(
    dataset_id: str,
    body: UpdateVisibilityRequest,
    session: AuthSessionDep,
) -> DatasetSummary:
    from uuid import UUID as _UUID

    from sqlalchemy import select as _select

    from app.data.models import Dataset, DataSource

    try:
        did = _UUID(dataset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found."
        ) from e

    stmt = (
        _select(Dataset, DataSource)
        .join(DataSource, Dataset.source_id == DataSource.id)
        .where(Dataset.id == did)
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    dataset, source = row
    dataset.visibility = body.visibility
    await session.commit()
    return _to_summary(dataset, source)


@datasets_router.get("/{dataset_id}/grants", response_model=DatasetGrantsResponse)
async def list_dataset_grants(dataset_id: str, session: AuthSessionDep) -> DatasetGrantsResponse:
    from uuid import UUID as _UUID

    from sqlalchemy import select as _select

    from app.auth.models import User
    from app.data.models import DatasetGrant

    try:
        did = _UUID(dataset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found."
        ) from e
    stmt = (
        _select(DatasetGrant, User)
        .join(User, DatasetGrant.user_id == User.id)
        .where(DatasetGrant.dataset_id == did)
        .order_by(DatasetGrant.created_at.desc())
    )
    grants = (await session.execute(stmt)).all()
    return DatasetGrantsResponse(
        grants=[
            DatasetGrantPublic(
                id=g.id,
                user_id=u.id,
                user_email=u.email,
                granted_at=g.created_at,
            )
            for g, u in grants
        ]
    )


@datasets_router.post(
    "/{dataset_id}/grants",
    status_code=status.HTTP_201_CREATED,
)
async def add_dataset_grant(
    dataset_id: str,
    body: GrantUserRequest,
    session: AuthSessionDep,
    user: CurrentUserDep,
) -> dict[str, str]:
    from uuid import UUID as _UUID

    from sqlalchemy.exc import IntegrityError

    from app.data.models import DatasetGrant

    try:
        did = _UUID(dataset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found."
        ) from e
    grant = DatasetGrant(dataset_id=did, user_id=body.user_id, granted_by=user.id)
    session.add(grant)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # Either the user already has a grant (unique constraint)
        # or the dataset_id is wrong — both 409 from a UX angle.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That user already has access.",
        ) from None
    return {"status": "ok"}


@datasets_router.delete(
    "/{dataset_id}/grants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_dataset_grant(
    dataset_id: str,
    user_id: str,
    session: AuthSessionDep,
) -> None:
    from uuid import UUID as _UUID

    from sqlalchemy import delete as _delete

    from app.data.models import DatasetGrant

    try:
        did = _UUID(dataset_id)
        uid = _UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found.") from e
    await session.execute(
        _delete(DatasetGrant).where(DatasetGrant.dataset_id == did, DatasetGrant.user_id == uid)
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Workspace members — used by the share UI to populate the user picker.
# Lives here for now; once we have a workspace settings page we move it
# to its own router.
# ---------------------------------------------------------------------------


workspace_router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])


@workspace_router.get("/members", response_model=WorkspaceMembersResponse)
async def list_workspace_members(
    session: AuthSessionDep,
    claims: AccessClaimsDep,
) -> WorkspaceMembersResponse:
    from sqlalchemy import select as _select

    from app.auth.models import TenantMembership, User

    stmt = (
        _select(User, TenantMembership)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .where(TenantMembership.tenant_id == claims.tenant_id)
        .order_by(User.email)
    )
    rows = (await session.execute(stmt)).all()
    return WorkspaceMembersResponse(
        members=[
            WorkspaceMember(user_id=u.id, email=u.email, role=str(m.role.value)) for u, m in rows
        ]
    )


__all__ = ["datasets_router", "sources_router", "workspace_router"]
