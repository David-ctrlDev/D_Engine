"""Pydantic schemas for the agent-conversation domain.

Same conventions as the rest of the codebase:

* request models forbid extra fields,
* response models project from ORM rows via ``from_attributes=True``,
* enum values come straight from the SQLAlchemy enums.
"""

from datetime import datetime
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
    token_usage: dict[str, int] | None
    created_at: datetime


class ConversationDetail(BaseModel):
    conversation: ConversationPublic
    messages: list[MessagePublic]


# ---------------------------------------------------------------------------
# Sending a message
# ---------------------------------------------------------------------------


class SendMessageRequest(_StrictModel):
    content: str = Field(min_length=1, max_length=8000)


class SendMessageResponse(BaseModel):
    """The newly-persisted ``user`` + ``assistant`` pair.

    Returning both keeps the frontend cache update trivial — it
    appends them to the local list without a separate fetch.
    """

    user_message: MessagePublic
    assistant_message: MessagePublic


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
    "SendMessageRequest",
    "SendMessageResponse",
    "UsableCredential",
    "UsableCredentialsResponse",
]
