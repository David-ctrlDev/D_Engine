"""Agent-conversation service layer.

Conventions match :mod:`app.data.service` and :mod:`app.llm.service`:

* mutating functions flush; the router commits,
* RLS gates visibility — service functions trust the DB,
* the API key is decrypted only when we're about to call the provider
  and is never re-persisted.

The interesting piece here is the **system prompt builder**:
:func:`_build_system_prompt` packs the dataset schema and the latest
profile run into a short briefing the agent reads at the start of every
turn. Without that context the agent has nothing useful to say —
"perfila mi CSV" with no schema visible is just hand-waving.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import desc, select

from app.agent.clients import ChatMessage, ProviderError, chat_completion
from app.agent.models import AgentConversation, AgentMessage, AgentMessageRole
from app.core import encryption
from app.data.models import Dataset, DataSource, ProfileRun, ProfileRunStatus
from app.llm.models import LlmCredential

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AgentError(Exception):
    """Root for agent-domain errors."""


class ConversationNotFoundError(AgentError):
    """Conversation doesn't exist or is invisible to the caller."""


class DatasetNotVisibleError(AgentError):
    """The dataset the user tried to chat about is invisible to them."""


class CredentialNotUsableError(AgentError):
    """The credential the user picked is invisible to them (RLS)."""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


# The agent gets a short briefing — schema + latest profile + a
# tight set of rules about how to talk. The audience is *not* technical
# (Head of Data, ops, business analysts); the system prompt enforces a
# plain-language tone and the suggestion-chip protocol the UI relies on.
_SYSTEM_TEMPLATE = """\
Eres el asistente de dataprep, una plataforma para preparar datos sin código.
Hablas con personas que NO son técnicas (jefes de área, analistas de negocio, gente de operaciones).
NO uses jerga técnica sin explicar. Usa lenguaje natural, frases cortas, bullets cuando enumeres.

Dataset actual: **{dataset_name}**.
Origen: {source_kind} — "{source_name}".

Esquema (columnas que existen en este dataset):
{schema}

{profile_section}

CÓMO RESPONDER

- Idioma: el mismo que use el usuario (español por defecto).
- Sé breve. Frases cortas. Bullets cuando enumeres.
- Cita columnas entre comillas: "categoría", "email".
- No inventes datos que no veas en el esquema o el análisis.
- No ejecutes acciones todavía. Por ahora SOLO conversas y propones.
  Si el usuario pide limpiar/deduplicar/normalizar, descríbelo paso a paso y di que próximamente podrás ejecutarlo.

OFRECER OPCIONES CLARAS (botones)

CASI SIEMPRE que termines un mensaje con una pregunta o con un plan que el usuario
debe aprobar, **termina tu mensaje** con UNA SOLA línea final en este formato exacto,
sin nada más después:

SUGGESTIONS:["Opción 1", "Opción 2", "Otra cosa…"]

Cuándo SÍ usar SUGGESTIONS:
- Cuando preguntes la intención del usuario (entrenar / chatbot / explorar).
- Después de mostrar un plan con varios pasos: ofrece "Empezar por el paso 1",
  "Explícame el paso N", "Ajustar el plan", "Otra cosa…".
- Cuando pidas confirmación sí/no: usa opciones claras ("Sí, procede", "Aún no").
- Cuando pidas que elija una columna, criterio o umbral: enumera 2-4 opciones plausibles.

Cuándo NO usar SUGGESTIONS:
- En respuestas puramente informativas que no piden decisión.
- Cuando ya estás explicando algo en detalle y el usuario no necesita elegir todavía.

Reglas para las opciones:
- 2 a 4 opciones.
- Cada opción: máximo ~7 palabras, en el idioma del usuario.
- Si una opción significa "ninguna de las anteriores", úsala como "Otra cosa…".

CUANDO EL USUARIO PIDA QUE PROCEDAS / EJECUTES

Si el usuario dice "procede", "dale", "empieza", "ejecuta", "hazlo":

- NO respondas únicamente "no puedo ejecutar todavía". Eso es un callejón sin salida.
- En su lugar: **explica con detalle el primer paso** del plan que propusiste —
  qué decisiones hay que tomar, qué pasaría con los datos, qué resultado esperarías.
- Si hay decisiones intermedias (qué columnas, qué umbral, qué criterio de
  duplicado, etc.), preséntalas como opciones con SUGGESTIONS.
- SOLO al final, en una frase breve, recuerda que la ejecución automática llega
  en próximas versiones — no como excusa, sino como contexto.

CUANDO INICIES LA CONVERSACIÓN (primer mensaje, sin que el usuario haya dicho nada)

1. Saluda brevemente: "Hola, soy tu asistente."
2. Resume el dataset en UNA frase: nombre del dataset, número de columnas, número de filas (si conoces row_count del análisis).
3. Si hubo análisis, lista en 2-4 bullets los problemas más relevantes que viste.
   Si NO hubo análisis aún, dilo y sugiérele ejecutarlo.
4. Pregunta qué quiere hacer con esos datos. Ofrece estas cuatro opciones (en este orden):

SUGGESTIONS:["Entrenar un modelo de IA con esto", "Usarlos en un chatbot", "Solo explorar y entender", "Otra cosa…"]

SIGUIENTES TURNOS

Según lo que el usuario elija, sigue guiándolo:

- "Entrenar un modelo de IA con esto" → pregunta qué quiere predecir (qué columna sería el objetivo)
  y qué tipo de modelo le sirve. Luego propón un plan de preparación de datos para entrenamiento.
- "Usarlos en un chatbot" → pregunta cómo va a usar el chatbot (atención al cliente, búsqueda en docs, etc.)
  y qué columna lleva el texto principal. Luego propón un plan para formatear los datos como contexto.
- "Solo explorar y entender" → propón una exploración guiada: empieza por las columnas con problemas,
  resume distribuciones, pregunta sobre qué columna quiere profundizar.
- "Otra cosa…" → pídele al usuario que describa con sus palabras qué necesita.
"""


def _format_schema(columns: list[dict[str, Any]]) -> str:
    """Pretty-print the dataset's columns for the prompt.

    Each row becomes ``- name (dtype, nullable)``. We deliberately don't
    paste sample values here — they may contain PII and the model
    doesn't need them to answer most "what's in my data?" questions.
    """
    if not columns:
        return "(sin columnas declaradas todavía)"
    lines: list[str] = []
    for c in columns:
        name = c.get("name", "?")
        dtype = c.get("dtype", "?")
        nullable = c.get("nullable", True)
        lines.append(f"- {name} ({dtype}{'/ nullable' if nullable else ''})")
    return "\n".join(lines)


_SUGGESTIONS_PATTERN = re.compile(r"SUGGESTIONS:\s*(\[[^\n]*\])\s*$", re.DOTALL)


def _parse_suggestions(text: str) -> tuple[str, list[str] | None]:
    """Pull a trailing ``SUGGESTIONS:[...]`` line out of an assistant turn.

    The LLM is instructed to emit chip options on a final, single line
    in a specific format (see :data:`_SYSTEM_TEMPLATE`). We strip that
    line from the user-visible text, JSON-parse the array, and return
    the cleaned text + the chips. If anything looks off we tolerate it
    by returning the original text and ``None`` — the chat still works,
    you just don't get buttons that turn.
    """
    m = _SUGGESTIONS_PATTERN.search(text)
    if m is None:
        return text.rstrip(), None
    try:
        parsed = json.loads(m.group(1))
    except ValueError:
        # JSONDecodeError is a subclass of ValueError; catching the
        # parent covers both. If the LLM forgot a quote or emitted
        # plain text, we silently degrade to "no chips".
        return text.rstrip(), None
    if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
        return text.rstrip(), None
    if not parsed:
        return text.rstrip(), None
    cleaned = text[: m.start()].rstrip()
    return cleaned, parsed


def _format_profile(profile: ProfileRun | None) -> str:
    """Brief summary of the latest *completed* profile run, if any."""
    if profile is None or profile.status is not ProfileRunStatus.completed:
        return (
            "Análisis de calidad: el usuario aún no ha ejecutado uno. "
            "Sugiere ejecutarlo si te preguntan sobre nulos, distintos o anomalías."
        )
    result = profile.result or {}
    row_count = result.get("row_count")
    cols = result.get("columns") or []
    high_null = [c for c in cols if isinstance(c, dict) and (c.get("null_pct") or 0) >= 0.2]
    parts = [f"Análisis de calidad ejecutado: {row_count or 0} filas."]
    if high_null:
        names = ", ".join(c.get("name", "?") for c in high_null[:5])
        parts.append(f"Columnas con muchos nulos (>=20%): {names}.")
    return " ".join(parts)


async def _build_system_prompt(
    session: AsyncSession,
    *,
    dataset: Dataset,
    source: DataSource,
) -> str:
    """Assemble the system message we send the agent every turn."""
    schema_columns: list[dict[str, Any]] = []
    # ``inferred_schema`` is JSONB on the Dataset (set at upload time).
    # We tolerate either a ``{columns: [...]}`` dict or a bare list
    # shape since slice A and slice C used slightly different layouts.
    raw_schema = dataset.inferred_schema or {}
    if isinstance(raw_schema, dict):
        cols = raw_schema.get("columns") or []
        if isinstance(cols, list):
            schema_columns = [c for c in cols if isinstance(c, dict)]
    elif isinstance(raw_schema, list):
        schema_columns = [c for c in raw_schema if isinstance(c, dict)]

    profile = (
        await session.execute(
            select(ProfileRun)
            .where(ProfileRun.dataset_id == dataset.id)
            .order_by(desc(ProfileRun.started_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    return _SYSTEM_TEMPLATE.format(
        dataset_name=dataset.name,
        source_kind=source.kind.value,
        source_name=source.name,
        schema=_format_schema(schema_columns),
        profile_section=_format_profile(profile),
    )


# ---------------------------------------------------------------------------
# Credential picker
# ---------------------------------------------------------------------------


async def list_usable_credentials(session: AsyncSession) -> list[LlmCredential]:
    """RLS hides credentials the caller can't see — we just SELECT
    everything visible and let the policies do the filtering."""
    rows = await session.execute(select(LlmCredential).order_by(LlmCredential.created_at.desc()))
    return list(rows.scalars().all())


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


async def list_conversations_for_dataset(
    session: AsyncSession, *, dataset_id: UUID
) -> list[AgentConversation]:
    """Conversations the caller created against a given dataset."""
    rows = await session.execute(
        select(AgentConversation)
        .where(AgentConversation.dataset_id == dataset_id)
        .order_by(AgentConversation.created_at.desc())
    )
    return list(rows.scalars().all())


async def get_conversation(session: AsyncSession, *, conversation_id: UUID) -> AgentConversation:
    """Fetch the conversation row. Returns ``ConversationNotFoundError``
    if RLS hides it."""
    convo = (
        await session.execute(
            select(AgentConversation).where(AgentConversation.id == conversation_id)
        )
    ).scalar_one_or_none()
    if convo is None:
        raise ConversationNotFoundError(str(conversation_id))
    return convo


async def get_conversation_with_messages(
    session: AsyncSession, *, conversation_id: UUID
) -> tuple[AgentConversation, list[AgentMessage]]:
    """Detail view — load the parent and all its messages in two queries.

    We filter ``system`` rows out of the visible transcript: those are
    our internal briefing prompt, not something the user wrote or
    needs to read back.
    """
    convo = await get_conversation(session, conversation_id=conversation_id)
    rows = await session.execute(
        select(AgentMessage)
        .where(
            AgentMessage.conversation_id == conversation_id,
            AgentMessage.role != AgentMessageRole.system,
        )
        .order_by(AgentMessage.created_at)
    )
    return convo, list(rows.scalars().all())


async def create_conversation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    dataset_id: UUID,
    credential_id: UUID,
    model: str,
) -> AgentConversation:
    """Create a new conversation row, no messages yet.

    Both ``dataset_id`` and ``credential_id`` are validated by RLS:
    if the caller can't see them, the matching SELECTs return None
    and we raise a friendly error instead of bouncing off a foreign-
    key violation.
    """
    # Verify the dataset is visible to the caller.
    dataset = (
        await session.execute(select(Dataset).where(Dataset.id == dataset_id))
    ).scalar_one_or_none()
    if dataset is None:
        raise DatasetNotVisibleError(str(dataset_id))

    # Verify the credential is visible (RLS on ``llm_credentials``
    # already does this — admins see all, members only see what
    # they've been granted / what's marked all_members).
    credential = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == credential_id))
    ).scalar_one_or_none()
    if credential is None:
        raise CredentialNotUsableError(str(credential_id))

    convo = AgentConversation(
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        created_by=user_id,
        credential_id=credential_id,
        model=model,
    )
    session.add(convo)
    await session.flush()
    return convo


# ---------------------------------------------------------------------------
# Sending a message — the agent loop itself
# ---------------------------------------------------------------------------


async def send_message(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    content: str,
) -> tuple[AgentMessage, AgentMessage]:
    """Append the user message, call the provider, append the response.

    Returns the (user_msg, assistant_msg) pair so the router can
    project them straight to the response without a re-fetch.
    """
    convo = await get_conversation(session, conversation_id=conversation_id)

    # Load the dataset + source so we can rebuild the system prompt.
    # We need them out-of-band of the conversation row; a single join
    # keeps it cheap.
    row = (
        await session.execute(
            select(Dataset, DataSource)
            .join(DataSource, Dataset.source_id == DataSource.id)
            .where(Dataset.id == convo.dataset_id)
        )
    ).one_or_none()
    if row is None:
        raise DatasetNotVisibleError(str(convo.dataset_id))
    dataset, source = row

    # Pull the credential and decrypt its API key. RLS still applies —
    # if the user lost access to the credential since starting the
    # conversation, this returns None and we bail.
    credential = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == convo.credential_id))
    ).scalar_one_or_none()
    if credential is None:
        raise CredentialNotUsableError(str(convo.credential_id))
    api_key = encryption.decrypt(credential.api_key_encrypted).decode()

    # Build the message list: fresh system prompt + history + new user turn.
    system_text = await _build_system_prompt(session, dataset=dataset, source=source)
    history_rows = (
        (
            await session.execute(
                select(AgentMessage)
                .where(
                    AgentMessage.conversation_id == conversation_id,
                    AgentMessage.role != AgentMessageRole.system,
                )
                .order_by(AgentMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    messages = [ChatMessage(role="system", content=system_text)]
    for m in history_rows:
        messages.append(ChatMessage(role=m.role.value, content=m.content))
    messages.append(ChatMessage(role="user", content=content))

    # Persist the user message *before* the provider call so a crash
    # mid-call still leaves a visible trail. We don't commit yet;
    # the router commits both messages together if the provider
    # responded ok, or we rollback if it didn't.
    user_msg = AgentMessage(
        conversation_id=conversation_id,
        role=AgentMessageRole.user,
        content=content,
    )
    session.add(user_msg)
    await session.flush()

    try:
        completion = await chat_completion(
            provider=credential.provider,
            api_key=api_key,
            base_url=credential.base_url,
            model=convo.model,
            messages=messages,
        )
    except ProviderError:
        # Roll back the user-message insert so a failed turn doesn't
        # leave a half-conversation. The router catches this and
        # surfaces an HTTP 502.
        await session.rollback()
        raise

    cleaned_text, suggestions = _parse_suggestions(completion.text)
    assistant_msg = AgentMessage(
        conversation_id=conversation_id,
        role=AgentMessageRole.assistant,
        content=cleaned_text or "(respuesta vacía del modelo)",
        suggestions=suggestions,
        token_usage=completion.token_usage,
    )
    session.add(assistant_msg)
    await session.flush()

    # If the conversation didn't have a title yet, derive one from the
    # first user message — first 80 chars, single line. The model
    # could do better, but for G2.1 this is fine.
    if convo.title is None:
        convo.title = _derive_title(content)
        await session.flush()

    return user_msg, assistant_msg


# ---------------------------------------------------------------------------
# Kickoff — the agent's *opening* turn
# ---------------------------------------------------------------------------


# Sentinel "user" message that nudges the LLM into the kickoff protocol.
# This message is NEVER persisted — it only lives long enough to elicit
# the response. The system prompt already tells the model what to do
# when it sees this trigger.
_KICKOFF_TRIGGER = (
    "(Sistema: el usuario acaba de abrir esta conversación. "
    "Aplica el protocolo de bienvenida descrito arriba: saluda, resume el dataset, "
    "lista los problemas más relevantes y ofrece las cuatro opciones de intención.)"
)


async def send_kickoff_turn(
    session: AsyncSession,
    *,
    conversation_id: UUID,
) -> AgentMessage:
    """Generate the agent's *opening* message — proactive, structured,
    intent-capture chips. Persists only an assistant turn (no user
    message: the user hasn't said anything yet)."""
    convo = await get_conversation(session, conversation_id=conversation_id)
    row = (
        await session.execute(
            select(Dataset, DataSource)
            .join(DataSource, Dataset.source_id == DataSource.id)
            .where(Dataset.id == convo.dataset_id)
        )
    ).one_or_none()
    if row is None:
        raise DatasetNotVisibleError(str(convo.dataset_id))
    dataset, source = row

    credential = (
        await session.execute(select(LlmCredential).where(LlmCredential.id == convo.credential_id))
    ).scalar_one_or_none()
    if credential is None:
        raise CredentialNotUsableError(str(convo.credential_id))
    api_key = encryption.decrypt(credential.api_key_encrypted).decode()

    system_text = await _build_system_prompt(session, dataset=dataset, source=source)
    messages = [
        ChatMessage(role="system", content=system_text),
        ChatMessage(role="user", content=_KICKOFF_TRIGGER),
    ]
    completion = await chat_completion(
        provider=credential.provider,
        api_key=api_key,
        base_url=credential.base_url,
        model=convo.model,
        messages=messages,
    )
    cleaned_text, suggestions = _parse_suggestions(completion.text)
    msg = AgentMessage(
        conversation_id=conversation_id,
        role=AgentMessageRole.assistant,
        content=cleaned_text or "(respuesta vacía del modelo)",
        suggestions=suggestions,
        token_usage=completion.token_usage,
    )
    session.add(msg)
    await session.flush()
    if convo.title is None:
        # The kickoff is a summary of the dataset; use its first line as
        # a usable title until the user picks an intent and we can
        # derive something better.
        first_line = next((ln for ln in cleaned_text.splitlines() if ln.strip()), "")
        convo.title = _derive_title(first_line)
        await session.flush()
    return msg


def _derive_title(text: str) -> str:
    one_line = " ".join(text.split())
    return one_line[:80]


__all__ = [
    "AgentError",
    "ConversationNotFoundError",
    "CredentialNotUsableError",
    "DatasetNotVisibleError",
    "create_conversation",
    "get_conversation",
    "get_conversation_with_messages",
    "list_conversations_for_dataset",
    "list_usable_credentials",
    "send_kickoff_turn",
    "send_message",
]
