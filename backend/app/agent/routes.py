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
    ResolvePendingActionRequest,
    SendMessageRequest,
    SendMessageResponse,
    UsableCredential,
    UsableCredentialsResponse,
)
from app.auth.dependencies import AccessClaimsDep, AuthSessionDep, CurrentUserDep
from app.data.deps import StorageDep
from app.transforms.service import WorkingCopyError

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
    storage: StorageDep,
) -> ConversationDetail:
    """Create a new conversation. When ``kickoff`` is true (the default),
    the agent's opening turn is generated server-side before the
    response returns — the chat lands on screen already populated
    with the diagnosis + intent chips.

    Commit semantics: we hold the conversation row + kickoff message
    in one transaction. If the LLM call fails we rollback so the user
    never sees an empty conversation that doesn't know how to start."""
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

    messages: list[MessagePublic] = []
    if body.kickoff:
        try:
            kickoff_msgs = await service.send_kickoff_turn(
                session,
                storage=storage,
                tenant_id=claims.tenant_id,
                user_id=user.id,
                conversation_id=convo.id,
            )
        except ProviderError as e:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"El proveedor rechazó la solicitud: {e}",
            ) from e
        except WorkingCopyError as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except service.DatasetNotVisibleError as e:  # pragma: no cover - just verified
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado."
            ) from e
        except service.CredentialNotUsableError as e:  # pragma: no cover - just verified
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esa conexión de IA.",
            ) from e
        messages = [MessagePublic.model_validate(m) for m in kickoff_msgs]

    await session.commit()
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
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    storage: StorageDep,
) -> SendMessageResponse:
    cid = _parse_uuid_or_404(conversation_id, "Conversación")
    try:
        user_msg, assistant_msgs = await service.send_message(
            session,
            storage=storage,
            tenant_id=claims.tenant_id,
            user_id=user.id,
            conversation_id=cid,
            content=body.content,
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
    except WorkingCopyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"El proveedor rechazó la solicitud: {e}",
        ) from e
    await session.commit()
    return SendMessageResponse(
        user_message=MessagePublic.model_validate(user_msg),
        assistant_messages=[MessagePublic.model_validate(m) for m in assistant_msgs],
    )


@router.post(
    "/conversations/{conversation_id}/pending-actions/{tool_call_id}/resolve",
    response_model=SendMessageResponse,
)
async def resolve_pending_action(
    conversation_id: str,
    tool_call_id: str,
    body: ResolvePendingActionRequest,
    session: AuthSessionDep,
    user: CurrentUserDep,
    claims: AccessClaimsDep,
    storage: StorageDep,
) -> SendMessageResponse:
    """Accept or reject a pending action proposed by the agent.

    On accept: the matching transform runs against the user's working
    copy, the result is fed back to the model, and the agent's next
    turn (the "ok, here's what happened" message + visualizations)
    lands in the response. On reject: a "user declined" tool_result
    is fed back; the agent typically replies with a follow-up
    question or an alternative."""
    cid = _parse_uuid_or_404(conversation_id, "Conversación")
    try:
        follow_ups = await service.resolve_pending_action(
            session,
            storage=storage,
            tenant_id=claims.tenant_id,
            user_id=user.id,
            conversation_id=cid,
            message_id=_parse_uuid_or_404(body.message_id, "Mensaje"),
            tool_call_id=tool_call_id,
            accept=body.accept,
        )
    except service.PendingActionError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except service.ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada."
        ) from e
    except service.CredentialNotUsableError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Perdiste el acceso a la conexión de IA usada por esta conversación.",
        ) from e
    except WorkingCopyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"El proveedor rechazó la solicitud: {e}",
        ) from e
    await session.commit()
    # There's no "user message" when resolving — the user clicked a
    # button, not typed text. We return only the agent's follow-up
    # turn(s) to be appended.
    return SendMessageResponse(
        user_message=None,
        assistant_messages=[MessagePublic.model_validate(m) for m in follow_ups],
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
