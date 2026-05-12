"""HTTP layer for ``/api/v1/conversations/*``.

Endpoints
---------

* ``GET    /api/v1/llm-credentials/usable`` — the credential picker
  data for the "Start conversation" modal. Returns the credentials
  the caller can actually use (RLS-filtered).

* ``GET    /api/v1/datasets/{id}/conversations`` — every conversation
  the caller has on a given dataset.

* ``POST   /api/v1/datasets/{id}/conversations`` — start a new
  conversation. Body picks the credential + model. Optional
  ``initial_message`` immediately runs one round-trip so the
  conversation lands non-empty.

* ``GET    /api/v1/conversations/{id}`` — detail view with all
  user/assistant messages in order.

* ``POST   /api/v1/conversations/{id}/messages`` — send a message,
  get the agent's reply back in the same response. (Streaming lands
  in G2.2.)

* ``DELETE /api/v1/conversations/{id}`` — soft-permanent delete.
  Cascades to ``agent_messages``.

Error mapping
-------------

* ``DatasetNotVisibleError`` / ``ConversationNotFoundError`` → 404
* ``CredentialNotUsableError``                              → 403
* ``ProviderError`` (the upstream LLM said no)              → 502
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.agent import service
from app.agent.clients import ProviderError
from app.agent.schemas import (
    ConversationCreateRequest,
    ConversationDetail,
    ConversationListResponse,
    ConversationPublic,
    MessagePublic,
    SendMessageRequest,
    SendMessageResponse,
    UsableCredential,
    UsableCredentialsResponse,
)
from app.auth.dependencies import AccessClaimsDep, AuthSessionDep, CurrentUserDep

router = APIRouter(prefix="/api/v1", tags=["agent"])


def _parse_uuid_or_404(raw: str, label: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} no encontrado."
        ) from e


# ---------------------------------------------------------------------------
# Credential picker
# ---------------------------------------------------------------------------


@router.get("/llm-credentials/usable", response_model=UsableCredentialsResponse)
async def list_usable_credentials(
    session: AuthSessionDep, _: CurrentUserDep
) -> UsableCredentialsResponse:
    creds = await service.list_usable_credentials(session)
    return UsableCredentialsResponse(
        credentials=[UsableCredential.model_validate(c) for c in creds]
    )


# ---------------------------------------------------------------------------
# Per-dataset conversation list + create
# ---------------------------------------------------------------------------


@router.get("/datasets/{dataset_id}/conversations", response_model=ConversationListResponse)
async def list_conversations(
    dataset_id: str, session: AuthSessionDep, _: CurrentUserDep
) -> ConversationListResponse:
    did = _parse_uuid_or_404(dataset_id, "Dataset")
    convos = await service.list_conversations_for_dataset(session, dataset_id=did)
    return ConversationListResponse(
        conversations=[ConversationPublic.model_validate(c) for c in convos]
    )


@router.post(
    "/datasets/{dataset_id}/conversations",
    response_model=ConversationDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    dataset_id: str,
    body: ConversationCreateRequest,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
) -> ConversationDetail:
    did = _parse_uuid_or_404(dataset_id, "Dataset")
    try:
        convo = await service.create_conversation(
            session,
            tenant_id=claims.tenant_id,
            user_id=user.id,
            dataset_id=did,
            credential_id=body.credential_id,
            model=body.model,
        )
    except service.DatasetNotVisibleError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado."
        ) from e
    except service.CredentialNotUsableError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esa conexión de IA.",
        ) from e
    await session.commit()
    # If the user supplied an opening message, fire one round-trip
    # before returning so the response already has a (user, assistant)
    # pair. This keeps the UI flow simple: one POST creates the chat.
    messages: list[MessagePublic] = []
    if body.initial_message:
        try:
            user_msg, assistant_msg = await service.send_message(
                session, conversation_id=convo.id, content=body.initial_message
            )
        except ProviderError as e:
            # The conversation still exists (we committed above); the
            # frontend will just show it empty and the user can try
            # sending a message again from the chat screen.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"El proveedor rechazó la solicitud: {e}",
            ) from e
        except service.ConversationNotFoundError as e:  # pragma: no cover - just created
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada."
            ) from e
        await session.commit()
        messages = [
            MessagePublic.model_validate(user_msg),
            MessagePublic.model_validate(assistant_msg),
        ]
    return ConversationDetail(
        conversation=ConversationPublic.model_validate(convo), messages=messages
    )


# ---------------------------------------------------------------------------
# Conversation detail + send message
# ---------------------------------------------------------------------------


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, session: AuthSessionDep, _: CurrentUserDep
) -> ConversationDetail:
    cid = _parse_uuid_or_404(conversation_id, "Conversación")
    try:
        convo, msgs = await service.get_conversation_with_messages(session, conversation_id=cid)
    except service.ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada."
        ) from e
    return ConversationDetail(
        conversation=ConversationPublic.model_validate(convo),
        messages=[MessagePublic.model_validate(m) for m in msgs],
    )


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    session: AuthSessionDep,
    _: CurrentUserDep,
) -> SendMessageResponse:
    cid = _parse_uuid_or_404(conversation_id, "Conversación")
    try:
        user_msg, assistant_msg = await service.send_message(
            session, conversation_id=cid, content=body.content
        )
    except service.ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada."
        ) from e
    except service.CredentialNotUsableError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Perdiste el acceso a la conexión de IA usada por esta conversación.",
        ) from e
    except ProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"El proveedor rechazó la solicitud: {e}",
        ) from e
    await session.commit()
    return SendMessageResponse(
        user_message=MessagePublic.model_validate(user_msg),
        assistant_message=MessagePublic.model_validate(assistant_msg),
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str, session: AuthSessionDep, _: CurrentUserDep
) -> None:
    cid = _parse_uuid_or_404(conversation_id, "Conversación")
    try:
        convo = await service.get_conversation(session, conversation_id=cid)
    except service.ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada."
        ) from e
    await session.delete(convo)
    await session.commit()


__all__ = ["router"]
