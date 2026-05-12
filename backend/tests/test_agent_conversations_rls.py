"""RLS invariants + happy-path agent loop for the conversations domain.

Coverage
--------

RLS:

* Cross-tenant isolation on ``agent_conversations``.
* Same-tenant member cannot read another member's conversation (private).
* Messages inherit the parent conversation's visibility.
* INSERT requires ``created_by = current_user`` and the chosen credential
  must be visible to the caller.

Happy path:

* End-to-end ``send_message`` with the provider patched out, asserting
  the system prompt embeds the dataset schema, the user + assistant
  messages are persisted in order, and ``title`` gets stamped from the
  first user turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from app.agent import service as agent_service
from app.agent.clients import ChatCompletion, ChatMessage
from app.agent.models import AgentConversation, AgentMessage, AgentMessageRole
from app.auth.models import TenantRole
from app.core import encryption
from app.data.models import (
    Dataset,
    DatasetKind,
    DataSource,
    DataSourceKind,
)
from app.db.rls import clear_request_context, set_request_context
from app.llm.models import LlmCredential, LlmMemberAccess, LlmProviderKind
from sqlalchemy import select

from tests.factories import make_membership, make_tenant, make_user

if TYPE_CHECKING:
    from uuid import UUID

    from app.auth.models import Tenant, User
    from sqlalchemy.ext.asyncio import AsyncSession


def _dummy_storage() -> Any:
    """Stand-in ``LocalFileStorage`` for tests that don't exercise the
    tool path. The chat stub never returns ``tool_calls``, so the
    agent service never reaches the working-copy code that would
    actually hit disk."""
    from pathlib import Path
    from tempfile import gettempdir

    from app.data.storage import LocalFileStorage

    return LocalFileStorage(Path(gettempdir()) / "dataprep-test-storage", max_bytes=1024)


# ---------------------------------------------------------------------------
# Workspace + dataset + credential fixture (in-test helper)
# ---------------------------------------------------------------------------


async def _seed(session: AsyncSession) -> tuple[Tenant, User, User, Tenant, User]:
    """Tenant A (owner_a + member_a) plus tenant B (owner_b).

    Same shape as the data-domain RLS suite — keeps tests legible.
    """
    a_tenant_id = uuid4()
    owner_a_id = uuid4()
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_tenant_id)
    a_tenant = await make_tenant(session, tenant_id=a_tenant_id, name="Acme")
    owner_a = await make_user(session, user_id=owner_a_id, email="owner-a@acme.io")
    await make_membership(session, user=owner_a, tenant=a_tenant, role=TenantRole.owner)
    await session.commit()

    member_a_id = uuid4()
    await set_request_context(session, user_id=member_a_id, tenant_id=a_tenant_id)
    member_a = await make_user(session, user_id=member_a_id, email="member-a@acme.io")
    await make_membership(session, user=member_a, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    b_tenant_id = uuid4()
    owner_b_id = uuid4()
    await set_request_context(session, user_id=owner_b_id, tenant_id=b_tenant_id)
    b_tenant = await make_tenant(session, tenant_id=b_tenant_id, name="Globex")
    owner_b = await make_user(session, user_id=owner_b_id, email="owner-b@globex.io")
    await make_membership(session, user=owner_b, tenant=b_tenant, role=TenantRole.owner)
    await session.commit()

    await clear_request_context(session)
    await session.commit()
    return a_tenant, owner_a, member_a, b_tenant, owner_b


async def _make_source(
    session: AsyncSession, *, tenant_id: UUID, creator_id: UUID, name: str = "src"
) -> DataSource:
    src = DataSource(
        tenant_id=tenant_id,
        created_by=creator_id,
        name=name,
        kind=DataSourceKind.csv,
        connection_config_encrypted=b"placeholder",
    )
    session.add(src)
    await session.flush()
    return src


async def _make_dataset(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    source_id: UUID,
    creator_id: UUID,
    name: str = "ds",
    inferred_schema: dict[str, Any] | None = None,
) -> Dataset:
    ds = Dataset(
        tenant_id=tenant_id,
        source_id=source_id,
        created_by=creator_id,
        name=name,
        kind=DatasetKind.table,
        locator={"schema": "public", "table": name},
        inferred_schema=inferred_schema
        or {
            "columns": [
                {"name": "id", "dtype": "int64", "nullable": False},
                {"name": "email", "dtype": "string", "nullable": True},
            ]
        },
    )
    session.add(ds)
    await session.flush()
    return ds


async def _make_credential(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    creator_id: UUID,
    member_access: LlmMemberAccess = LlmMemberAccess.all_members,
    nickname: str = "shared",
) -> LlmCredential:
    cred = LlmCredential(
        tenant_id=tenant_id,
        created_by=creator_id,
        provider=LlmProviderKind.anthropic,
        nickname=nickname,
        api_key_encrypted=encryption.encrypt(b"sk-test-not-real"),
        member_access=member_access,
    )
    session.add(cred)
    await session.flush()
    return cred


# ===========================================================================
# Cross-tenant isolation
# ===========================================================================


async def test_cross_tenant_conversation_invisible(session: AsyncSession) -> None:
    """A conversation in tenant B is invisible to tenant A's owner."""
    a_tenant, owner_a, _, b_tenant, owner_b = await _seed(session)
    a_id, owner_a_id = a_tenant.id, owner_a.id
    b_id, owner_b_id = b_tenant.id, owner_b.id

    await set_request_context(session, user_id=owner_b_id, tenant_id=b_id)
    b_src = await _make_source(session, tenant_id=b_id, creator_id=owner_b_id, name="b_src")
    b_ds = await _make_dataset(session, tenant_id=b_id, source_id=b_src.id, creator_id=owner_b_id)
    b_cred = await _make_credential(
        session, tenant_id=b_id, creator_id=owner_b_id, nickname="b_cred"
    )
    session.add(
        AgentConversation(
            tenant_id=b_id,
            dataset_id=b_ds.id,
            created_by=owner_b_id,
            credential_id=b_cred.id,
            model="claude-sonnet-4-5",
        )
    )
    await session.commit()

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    rows = (await session.execute(select(AgentConversation))).scalars().all()
    assert rows == []


# ===========================================================================
# Privacy within a tenant
# ===========================================================================


async def test_conversation_invisible_to_other_member_same_tenant(
    session: AsyncSession,
) -> None:
    """Two members of the same tenant don't see each other's conversations.

    The workspace **owner**, on the other hand, *does* see them — that's
    the governance override the policy intentionally allows.
    """
    a_tenant, owner_a, member_a, _, _ = await _seed(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    # Owner registers a credential the whole workspace can use.
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(session, tenant_id=a_id, creator_id=owner_a_id)
    await session.commit()

    # member_a creates their own private conversation.
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="s")
    ds = await _make_dataset(
        session, tenant_id=a_id, source_id=src.id, creator_id=member_a_id, name="ds1"
    )
    session.add(
        AgentConversation(
            tenant_id=a_id,
            dataset_id=ds.id,
            created_by=member_a_id,
            credential_id=cred.id,
            model="claude-sonnet-4-5",
        )
    )
    await session.commit()

    # A second, unrelated member of the same tenant cannot see it.
    other_id = uuid4()
    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    other = await make_user(session, user_id=other_id, email="other@acme.io")
    await make_membership(session, user=other, tenant=a_tenant, role=TenantRole.member)
    await session.commit()
    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    rows = (await session.execute(select(AgentConversation))).scalars().all()
    assert rows == []

    # The workspace owner *does* see it (governance override).
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    rows = (await session.execute(select(AgentConversation))).scalars().all()
    assert len(rows) == 1
    assert rows[0].created_by == member_a_id


# ===========================================================================
# Messages inherit visibility
# ===========================================================================


async def test_messages_inherit_parent_visibility(session: AsyncSession) -> None:
    """If the user can't see the parent conversation, they can't see its
    messages either."""
    a_tenant, owner_a, _, _, _ = await _seed(session)
    a_id, owner_a_id = a_tenant.id, owner_a.id

    # Owner creates a private conversation and a message in it.
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(session, tenant_id=a_id, creator_id=owner_a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=owner_a_id, name="s")
    ds = await _make_dataset(session, tenant_id=a_id, source_id=src.id, creator_id=owner_a_id)
    convo = AgentConversation(
        tenant_id=a_id,
        dataset_id=ds.id,
        created_by=owner_a_id,
        credential_id=cred.id,
        model="claude-sonnet-4-5",
    )
    session.add(convo)
    await session.flush()
    session.add(
        AgentMessage(
            conversation_id=convo.id,
            role=AgentMessageRole.user,
            content="hola",
        )
    )
    await session.commit()

    # A different member of the same tenant can't see the messages.
    other_id = uuid4()
    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    other = await make_user(session, user_id=other_id, email="o@acme.io")
    await make_membership(session, user=other, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    rows = (await session.execute(select(AgentMessage))).scalars().all()
    assert rows == []


# ===========================================================================
# send_message — happy path with a stubbed provider
# ===========================================================================


@pytest.fixture
def stub_chat_completion(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the provider client so tests don't hit real APIs.

    Records the exact arguments that would have been sent and returns
    a canned ``ChatCompletion``. Tests inspect ``captured["messages"]``
    to assert what the agent actually saw.
    """
    captured: dict[str, Any] = {}

    async def fake(
        *,
        provider: LlmProviderKind,
        api_key: str,
        base_url: str | None,
        model: str,
        messages: list[ChatMessage],
        tools: Any = None,
    ) -> ChatCompletion:
        captured["provider"] = provider
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        captured["model"] = model
        captured["messages"] = messages
        return ChatCompletion(
            text="Tu dataset tiene una columna id sin nulos y una columna email opcional.",
            token_usage={"prompt": 42, "completion": 21, "total": 63},
        )

    monkeypatch.setattr(agent_service, "chat_completion", fake)
    return captured


async def test_send_message_happy_path(
    session: AsyncSession, stub_chat_completion: dict[str, Any]
) -> None:
    """End-to-end: owner creates a conversation, sends a message, gets
    the stubbed assistant reply, the messages persist in order."""
    a_tenant, owner_a, _, _, _ = await _seed(session)
    a_id, owner_a_id = a_tenant.id, owner_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(session, tenant_id=a_id, creator_id=owner_a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=owner_a_id, name="sales")
    ds = await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=owner_a_id,
        name="customers",
    )
    convo = await agent_service.create_conversation(
        session,
        tenant_id=a_id,
        user_id=owner_a_id,
        dataset_id=ds.id,
        credential_id=cred.id,
        model="claude-sonnet-4-5",
    )
    await session.commit()
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)

    user_msg, assistant_msgs = await agent_service.send_message(
        session,
        storage=_dummy_storage(),
        tenant_id=a_id,
        user_id=owner_a_id,
        conversation_id=convo.id,
        content="¿Qué ves en mis datos?",
    )
    await session.commit()
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)

    # The stub captured the briefing: schema columns appear in the
    # system prompt, the user turn lands last.
    msgs = stub_chat_completion["messages"]
    assert msgs[0].role == "system"
    assert "customers" in msgs[0].content
    assert "email" in msgs[0].content
    assert msgs[-1].role == "user"
    assert msgs[-1].content == "¿Qué ves en mis datos?"

    # Persistence: in order, no system rows visible to the UI.
    rows = (
        (
            await session.execute(
                select(AgentMessage)
                .where(AgentMessage.conversation_id == convo.id)
                .order_by(AgentMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert [r.role for r in rows] == [AgentMessageRole.user, AgentMessageRole.assistant]
    assert rows[0].content == "¿Qué ves en mis datos?"
    assert "id" in rows[1].content or "email" in rows[1].content
    assert rows[1].token_usage == {"prompt": 42, "completion": 21, "total": 63}

    # Title got stamped from the first user message.
    refreshed = (
        await session.execute(select(AgentConversation).where(AgentConversation.id == convo.id))
    ).scalar_one()
    assert refreshed.title == "¿Qué ves en mis datos?"

    # Sanity: the agent received the *decrypted* key (the stub captured it).
    assert stub_chat_completion["api_key"] == "sk-test-not-real"
    assert user_msg.role == AgentMessageRole.user
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].role == AgentMessageRole.assistant


# ===========================================================================
# Kickoff turn + SUGGESTIONS parser
# ===========================================================================


@pytest.fixture
def stub_chat_completion_with_chips(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Variant of the chat stub that emits a kickoff-style response —
    text plus a trailing ``SUGGESTIONS:[...]`` line, the format the
    LLM is supposed to use for intent-capture chips."""
    captured: dict[str, Any] = {}

    async def fake(
        *,
        provider: LlmProviderKind,
        api_key: str,
        base_url: str | None,
        model: str,
        messages: list[ChatMessage],
        tools: Any = None,
    ) -> ChatCompletion:
        captured["messages"] = messages
        text = (
            "Hola, soy tu asistente.\n\n"
            'Veo que cargaste "customers" — 2 columnas.\n\n'
            'Detecté que la columna "email" puede tener nulos.\n\n'
            "¿Qué te gustaría hacer con estos datos?\n\n"
            'SUGGESTIONS:["Entrenar un modelo de IA con esto", '
            '"Usarlos en un chatbot", "Solo explorar y entender", "Otra cosa…"]'
        )
        return ChatCompletion(
            text=text,
            token_usage={"prompt": 100, "completion": 50, "total": 150},
        )

    monkeypatch.setattr(agent_service, "chat_completion", fake)
    return captured


async def test_kickoff_turn_produces_assistant_with_chips(
    session: AsyncSession, stub_chat_completion_with_chips: dict[str, Any]
) -> None:
    """The agent-led opening: no user message persisted, single
    assistant turn with its ``suggestions`` populated from the
    ``SUGGESTIONS:[...]`` line. The user-visible content has the
    trailing chip line stripped."""
    a_tenant, owner_a, _, _, _ = await _seed(session)
    a_id, owner_a_id = a_tenant.id, owner_a.id

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    cred = await _make_credential(session, tenant_id=a_id, creator_id=owner_a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=owner_a_id, name="src")
    ds = await _make_dataset(
        session, tenant_id=a_id, source_id=src.id, creator_id=owner_a_id, name="customers"
    )
    convo = await agent_service.create_conversation(
        session,
        tenant_id=a_id,
        user_id=owner_a_id,
        dataset_id=ds.id,
        credential_id=cred.id,
        model="claude-sonnet-4-5",
    )
    await session.commit()
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)

    kickoffs = await agent_service.send_kickoff_turn(
        session,
        storage=_dummy_storage(),
        tenant_id=a_id,
        user_id=owner_a_id,
        conversation_id=convo.id,
    )
    kickoff = kickoffs[0]
    await session.commit()

    # The trigger we sent the LLM is *not* persisted — only the
    # assistant turn exists for the conversation.
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    rows = (
        (
            await session.execute(
                select(AgentMessage)
                .where(AgentMessage.conversation_id == convo.id)
                .order_by(AgentMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].role == AgentMessageRole.assistant
    # The SUGGESTIONS line is stripped from the user-visible content.
    assert "SUGGESTIONS:" not in rows[0].content
    assert "soy tu asistente" in rows[0].content
    # The chips landed in the suggestions column, in order.
    assert rows[0].suggestions == [
        "Entrenar un modelo de IA con esto",
        "Usarlos en un chatbot",
        "Solo explorar y entender",
        "Otra cosa…",
    ]
    assert kickoff.role == AgentMessageRole.assistant


def test_parse_suggestions_handles_messy_inputs() -> None:
    """The parser tolerates the LLM emitting the line in different
    shapes, and degrades to (text, None) when the JSON is broken."""
    from app.agent.service import _parse_suggestions

    # Happy path.
    cleaned, sug = _parse_suggestions('Hola.\n\nSUGGESTIONS:["A", "B", "C"]')
    assert cleaned == "Hola."
    assert sug == ["A", "B", "C"]

    # Trailing whitespace tolerated.
    cleaned, sug = _parse_suggestions('Hola.\n\nSUGGESTIONS:["A", "B"]\n  \n')
    assert cleaned == "Hola."
    assert sug == ["A", "B"]

    # No SUGGESTIONS line at all — text passes through, no chips.
    cleaned, sug = _parse_suggestions("Solo un párrafo sin opciones.")
    assert cleaned == "Solo un párrafo sin opciones."
    assert sug is None

    # Malformed JSON — fall back to original text, no chips.
    cleaned, sug = _parse_suggestions("Hola.\n\nSUGGESTIONS:[broken]")
    assert "Hola." in cleaned
    assert sug is None

    # Empty list — counts as "no chips".
    cleaned, sug = _parse_suggestions("Hola.\n\nSUGGESTIONS:[]")
    assert sug is None
