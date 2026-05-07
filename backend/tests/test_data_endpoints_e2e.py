"""End-to-end tests for /api/v1/sources and /api/v1/datasets.

The user flow under test (slice A):

1. Register, verify, log in — borrowed from the auth E2E suite.
2. Upload a CSV via ``POST /api/v1/sources/upload`` (multipart).
3. List datasets — the new one shows up.
4. Fetch the detail — schema columns + sample rows.
5. A second tenant cannot see the first tenant's dataset (RLS smoke
   test at the HTTP layer, complementing ``test_data_models_rls.py``).
"""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from app.auth.cookies import ACCESS_COOKIE_NAME
from app.auth.email import CapturingEmailSender
from app.auth.routes import get_email_sender
from app.data.deps import get_storage
from app.data.storage import LocalFileStorage
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


STRONG_PASSWORD = "velvet-harbor-pumice-galaxy"
_TOKEN_PAT = re.compile(r"token=([A-Za-z0-9_\-]+)")


def _extract_token(text_body: str) -> str:
    match = _TOKEN_PAT.search(text_body)
    assert match, f"no token in body: {text_body!r}"
    return match.group(1)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="session")
async def client(
    test_engine: AsyncEngine,
    admin_engine: AsyncEngine,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[AsyncClient]:
    """ASGI client with email + storage overridden, schema rebuilt."""
    sender = CapturingEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender

    storage_root: Path = tmp_path_factory.mktemp("uploads")
    test_storage = LocalFileStorage(storage_root, max_bytes=10 * 1024 * 1024)
    app.dependency_overrides[get_storage] = lambda: test_storage

    # Same monkey-patch pattern as the auth E2E test — keep
    # async_session_maker pointed at the test DB.
    from app.db import session as session_mod

    original_engine = session_mod.engine
    original_maker = session_mod.async_session_maker
    session_mod.engine = test_engine
    session_mod.async_session_maker = original_maker.__class__(
        test_engine, expire_on_commit=False, class_=original_maker.class_
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            ac._email_sender = sender  # type: ignore[attr-defined]
            yield ac
    finally:
        session_mod.engine = original_engine
        session_mod.async_session_maker = original_maker
        app.dependency_overrides.pop(get_email_sender, None)
        app.dependency_overrides.pop(get_storage, None)
        async with admin_engine.begin() as conn:
            await conn.exec_driver_sql(
                "TRUNCATE TABLE profile_runs, dataset_grants, datasets, "
                "data_sources, audit_log, auth_tokens, refresh_tokens, "
                "mfa_recovery_codes, mfa_methods, tenant_memberships, "
                "users, tenants CASCADE"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _signup_and_login(client: AsyncClient, email: str, workspace_name: str) -> None:
    """Register, verify, log in. Leaves the access cookie on the client."""
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": STRONG_PASSWORD, "workspace_name": workspace_name},
    )
    assert r.status_code == 201, r.text

    sender: CapturingEmailSender = client._email_sender  # type: ignore[attr-defined]
    verify_token = _extract_token(sender.outbox[-1].text_body)

    r = await client.post("/api/v1/auth/verify-email", json={"token": verify_token})
    assert r.status_code == 200, r.text

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    assert r.status_code == 200, r.text


def _csv_bytes() -> bytes:
    return b"id,name,price,in_stock\n1,Apple,0.50,true\n2,Banana,0.20,true\n3,Cherry,2.10,false\n"


# ===========================================================================
# 1. Happy path — upload, list, detail
# ===========================================================================


async def test_upload_list_detail_happy_path(client: AsyncClient) -> None:
    await _signup_and_login(client, "alice@acme.io", "Acme Inc")

    # --- upload ------------------------------------------------------------
    files = {"file": ("products.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    data = {"dataset_name": "Products"}
    r = await client.post("/api/v1/sources/upload", files=files, data=data)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["dataset"]["name"] == "Products"
    assert body["dataset"]["source_kind"] == "csv"
    assert body["dataset"]["visibility"] == "private"

    # 4 columns inferred. Polars infers Int64/String/Float64/Boolean.
    cols_by_name = {c["name"]: c for c in body["columns"]}
    assert set(cols_by_name) == {"id", "name", "price", "in_stock"}
    assert cols_by_name["id"]["dtype"] == "Int64"
    assert cols_by_name["price"]["dtype"] == "Float64"
    assert cols_by_name["in_stock"]["dtype"] == "Boolean"
    # Sample values come straight from the head of the CSV.
    assert cols_by_name["name"]["sample_values"][0] == "Apple"

    # --- list --------------------------------------------------------------
    r = await client.get("/api/v1/datasets")
    assert r.status_code == 200, r.text
    listing = r.json()["datasets"]
    assert len(listing) == 1
    assert listing[0]["name"] == "Products"
    dataset_id = listing[0]["id"]

    # --- detail ------------------------------------------------------------
    r = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["name"] == "Products"
    assert detail["source"]["kind"] == "csv"
    assert len(detail["columns"]) == 4
    # We re-read the file from disk for sample_rows on detail.
    assert len(detail["sample_rows"]) == 3
    assert detail["sample_rows"][0]["name"] == "Apple"


# ===========================================================================
# 2. Authentication required
# ===========================================================================


async def test_upload_requires_auth(client: AsyncClient) -> None:
    files = {"file": ("x.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")}
    r = await client.post("/api/v1/sources/upload", files=files, data={"dataset_name": "X"})
    assert r.status_code == 401


async def test_list_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/datasets")
    assert r.status_code == 401


# ===========================================================================
# 3. Cross-tenant isolation at the HTTP layer
# ===========================================================================


async def test_other_tenant_cannot_see_or_fetch_dataset(client: AsyncClient) -> None:
    # Tenant A uploads a dataset.
    await _signup_and_login(client, "alice@acme.io", "Acme Inc")
    files = {"file": ("secret.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    r = await client.post(
        "/api/v1/sources/upload",
        files=files,
        data={"dataset_name": "Secret"},
    )
    assert r.status_code == 201
    secret_id = r.json()["dataset"]["id"]

    # Logout, then register tenant B from scratch.
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    # Drop any leftover cookie. ``logout`` clears them server-side but
    # httpx still has the values in its jar by name, so be explicit.
    client.cookies.delete(ACCESS_COOKIE_NAME)

    await _signup_and_login(client, "bob@globex.io", "Globex")

    # Tenant B's listing is empty.
    r = await client.get("/api/v1/datasets")
    assert r.status_code == 200
    assert r.json()["datasets"] == []

    # Direct fetch of A's dataset → 404 (RLS made the row invisible).
    r = await client.get(f"/api/v1/datasets/{secret_id}")
    assert r.status_code == 404


# ===========================================================================
# 4. Bad inputs
# ===========================================================================


async def test_upload_rejects_unsupported_extension(client: AsyncClient) -> None:
    await _signup_and_login(client, "alice@acme.io", "Acme Inc")
    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = await client.post(
        "/api/v1/sources/upload",
        files=files,
        data={"dataset_name": "Notes"},
    )
    assert r.status_code == 422
    assert "unsupported file extension" in r.json()["detail"].lower()


async def test_upload_rejects_duplicate_filename(client: AsyncClient) -> None:
    """The ``data_sources`` unique constraint is on ``(tenant_id, name)``,
    where the source's name is the original filename. Uploading the
    same file twice — even with a different ``dataset_name`` — must
    fail with 409.

    Two *different* files producing two datasets with the same display
    name is intentionally allowed, because each upload spawns its own
    source and the dataset uniqueness is scoped per-source. We revisit
    that decision when slice C lands DB sources."""
    await _signup_and_login(client, "alice@acme.io", "Acme Inc")
    files1 = {"file": ("dup.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    r = await client.post("/api/v1/sources/upload", files=files1, data={"dataset_name": "First"})
    assert r.status_code == 201
    files2 = {"file": ("dup.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    r = await client.post("/api/v1/sources/upload", files=files2, data={"dataset_name": "Second"})
    assert r.status_code == 409


async def test_get_dataset_invalid_uuid_returns_404(client: AsyncClient) -> None:
    await _signup_and_login(client, "alice@acme.io", "Acme Inc")
    r = await client.get("/api/v1/datasets/not-a-uuid")
    assert r.status_code == 404
