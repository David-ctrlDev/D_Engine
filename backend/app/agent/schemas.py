"""Pydantic schemas for the agent-conversation domain.

Same conventions as the rest of the codebase:

* request models forbid extra fields,
* response models project from ORM rows via ``from_attributes=True``,
* enum values come straight from the SQLAlchemy enums.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agent.models import AgentMessageRole
from app.llm.models import LlmProviderKind


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


class ConversationCreateRequest(_StrictModel):
    """Start a new chat thread on a dataset.

    The user picks which BYOK credential to spend against and which
    model. Both have to be valid for the current tenant — the service
    layer + RLS enforce that.

    ``kickoff`` (default ``True``) tells the backend to immediately
    generate the agent's *opening turn* — a structured introduction
    with the dataset summary, the problems detected, and intent-
    capture chips. The user sees the chat already populated; they
    don't have to type first.
    """

    credential_id: UUID
    model: str = Field(min_length=1, max_length=120)
    kickoff: bool = True


class ConversationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    credential_id: UUID
    model: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationPublic]


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: AgentMessageRole
    content: str
    # ``["Entrenar un modelo", ...]`` — intent-capture chips the agent
    # attached. Only ever populated on ``assistant`` rows. The
    # frontend renders them as buttons; clicking one sends the chip
    # text as the next user message.
    suggestions: list[str] | None = None
    # Typed inline viz specs (histograms, before/after bars, pending-
    # action cards). The frontend dispatches each entry's ``kind`` to
    # a chart component. ``None`` for plain-text turns.
    visualizations: list[dict[str, Any]] | None = None
    # Names of tools the agent actually executed on this turn. The
    # frontend renders them as small "✓ dedupe · fillna" chips under
    # the agent label so the user has *visual proof* of what really
    # ran (vs what the agent might claim in its text). Computed from
    # the ``tool_payload`` JSONB column server-side.
    executed_tools: list[str] = []
    token_usage: dict[str, int] | None
    created_at: datetime

    @classmethod
    def model_validate(cls, obj: Any, **kw: Any) -> MessagePublic:
        # Derive ``executed_tools`` from the persisted ``tool_payload``
        # blob before pydantic copies the rest of the fields. We can't
        # use a SQLAlchemy hybrid_property because the blob shape lives
        # in two places (the agent's tool_use blocks AND the internal
        # tool_use_id results) — easier to compute here, where we own
        # the projection.
        names: list[str] = []
        payload = getattr(obj, "tool_payload", None) or (
            obj.get("tool_payload") if isinstance(obj, dict) else None
        )
        if isinstance(payload, dict):
            calls = payload.get("tool_calls") or []
            if isinstance(calls, list):
                for c in calls:
                    if isinstance(c, dict) and isinstance(c.get("name"), str):
                        names.append(c["name"])
        validated = super().model_validate(obj, **kw)
        # Re-attach computed field — pydantic doesn't surface unknown
        # attrs from the ORM row.
        object.__setattr__(validated, "executed_tools", names)
        return validated


class ConversationDetail(BaseModel):
    conversation: ConversationPublic
    messages: list[MessagePublic]


# ---------------------------------------------------------------------------
# Sending a message
# ---------------------------------------------------------------------------


class SendMessageRequest(_StrictModel):
    content: str = Field(min_length=1, max_length=8000)


class SendMessageResponse(BaseModel):
    """The newly-persisted user + assistant turn(s).

    The agent loop can produce multiple assistant rows in one
    user turn (e.g. one with a tool_use that ran ``inspect_column``,
    then one with the diagnosis + intent chips). The frontend
    appends them in order to the local transcript.

    ``user_message`` is ``None`` when the response comes from a
    button click (e.g. accepting a pending action) rather than a
    typed message.
    """

    user_message: MessagePublic | None
    assistant_messages: list[MessagePublic]


class ResolvePendingActionRequest(_StrictModel):
    """Accept or reject a pending-action card the agent emitted.

    ``message_id`` is the id of the assistant message that carries
    the pending action; ``accept`` is the choice. The route uses the
    URL's ``tool_call_id`` to find the specific action inside that
    message (one assistant turn could propose more than one action,
    each gets resolved individually)."""

    message_id: str
    accept: bool


# ---------------------------------------------------------------------------
# Usable credentials (the picker on the "start conversation" form)
# ---------------------------------------------------------------------------


class UsableCredential(BaseModel):
    """A credential the calling user can pick for a new conversation.

    Re-shapes ``LlmCredentialPublic`` to the fields the picker actually
    needs and adds the provider's display name so the UI doesn't have
    to look it up from the catalogue."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nickname: str
    provider: LlmProviderKind
    model_default: str | None


class UsableCredentialsResponse(BaseModel):
    credentials: list[UsableCredential]


__all__ = [
    "ConversationCreateRequest",
    "ConversationDetail",
    "ConversationListResponse",
    "ConversationPublic",
    "MessagePublic",
    "ResolvePendingActionRequest",
    "SendMessageRequest",
    "SendMessageResponse",
    "UsableCredential",
    "UsableCredentialsResponse",
]
