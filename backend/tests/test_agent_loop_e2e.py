"""End-to-end test for the agentic loop.

Regression guard for the bug where the agent "only worked as a chat":
``agent_messages`` was append-only (no UPDATE RLS policy), but the loop
updates a freshly-inserted assistant row to pin the visualizations a tool
produced. With RLS denying the UPDATE, every tool-running turn raised
``StaleDataError`` and rolled back — text turns survived, agentic
execution didn't. Migration 0007 adds the UPDATE policy; this test drives
the whole path with a stubbed ``chat_completion`` (no real API key) and
asserts the tool runs, the data mutates, and the chart lands on the
message.
"""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from app.agent import service as agent_service
from app.agent.clients import ChatCompletion, ToolCall
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


@pytest_asyncio.fixture(loop_scope="session")
async def client(
    test_engine: AsyncEngine,
    admin_engine: AsyncEngine,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[AsyncClient]:
    sender = CapturingEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    storage_root: Path = tmp_path_factory.mktemp("uploads")
    test_storage = LocalFileStorage(storage_root, max_bytes=10 * 1024 * 1024)
    app.dependency_overrides[get_storage] = lambda: test_storage

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
                "TRUNCATE TABLE dataset_operations, dataset_working_copies, "
                "agent_messages, agent_conversations, llm_credential_grants, "
                "llm_credentials, profile_runs, dataset_grants, datasets, "
                "data_sources, audit_log, auth_tokens, refresh_tokens, "
                "mfa_recovery_codes, mfa_methods, tenant_memberships, "
                "users, tenants CASCADE"
            )


async def _signup_and_login(client: AsyncClient, email: str, workspace: str) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": STRONG_PASSWORD, "workspace_name": workspace},
    )
    assert r.status_code == 201, r.text
    sender: CapturingEmailSender = client._email_sender  # type: ignore[attr-defined]
    token = _TOKEN_PAT.search(sender.outbox[-1].text_body).group(1)
    r = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": STRONG_PASSWORD})
    assert r.status_code == 200, r.text


# CSV with a duplicate email so dedupe actually removes a row.
_CSV = b"email,name,country\na@x.com,Ana,spain\na@x.com,Ana,Spain\nb@x.com,Beto,mexico\n"


async def test_agent_executes_tools_when_llm_returns_tool_calls(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _signup_and_login(client, "alice@acme.io", "Acme")

    # Upload a dataset.
    files = {"file": ("people.csv", io.BytesIO(_CSV), "text/csv")}
    r = await client.post("/api/v1/sources/upload", files=files, data={"dataset_name": "People"})
    assert r.status_code == 201, r.text
    dataset_id = r.json()["dataset"]["id"]

    # Register a (fake) Anthropic credential — key is never used because
    # chat_completion is stubbed.
    r = await client.post(
        "/api/v1/llm-credentials",
        json={
            "provider": "anthropic",
            "nickname": "test",
            "api_key": "sk-fake",
            "model_default": "claude-x",
        },
    )
    assert r.status_code == 201, r.text
    credential_id = r.json()["id"]

    # Script the LLM: first call -> dedupe tool; second call -> final text.
    calls: list[int] = []

    async def fake_chat_completion(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(1)
        n = len(calls)
        if n == 1:
            return ChatCompletion(
                text="",
                token_usage={"prompt": 1, "completion": 1, "total": 2},
                tool_calls=(
                    ToolCall(
                        id="call_1",
                        name="dedupe",
                        args={"columns": ["email"], "keep": "first", "normalize_text": True},
                    ),
                ),
                stop_reason="tool_use",
            )
        return ChatCompletion(
            text="Listo, eliminé los duplicados.",
            token_usage={"prompt": 2, "completion": 2, "total": 4},
            tool_calls=(),
            stop_reason="end_turn",
        )

    monkeypatch.setattr(agent_service, "chat_completion", fake_chat_completion)

    # Create conversation WITHOUT kickoff (kickoff would burn a stubbed call).
    r = await client.post(
        f"/api/v1/datasets/{dataset_id}/conversations",
        json={"credential_id": credential_id, "model": "claude-x", "kickoff": False},
    )
    assert r.status_code == 201, r.text
    conversation_id = r.json()["conversation"]["id"]

    # Send a message — this should force a tool call on iter 0.
    r = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Limpia los duplicados por email."},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    # The tool actually executed (proof: the ground-truth badge field).
    executed = [t for m in body["assistant_messages"] for t in m["executed_tools"]]
    assert "dedupe" in executed, "Agent did NOT execute the dedupe tool"

    # The visualization the tool produced was pinned to the assistant
    # message — this is the UPDATE that used to fail with StaleDataError.
    all_viz = [v for m in body["assistant_messages"] for v in (m["visualizations"] or [])]
    assert all_viz, "No visualization attached to the assistant turn"

    # The data actually mutated: the duplicate 'a@x.com' row was dropped
    # (3 rows -> 2). The working copy reflects the new state.
    r = await client.get(f"/api/v1/datasets/{dataset_id}/working-copy")
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 2
