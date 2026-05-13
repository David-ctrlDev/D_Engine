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

from app.agent.clients import ChatMessage, ProviderError, ToolCall, chat_completion
from app.agent.models import AgentConversation, AgentMessage, AgentMessageRole
from app.agent.tools import PENDING_ACTION_TOOLS, TOOLS
from app.core import encryption
from app.data.models import Dataset, DataSource, ProfileRun, ProfileRunStatus
from app.llm.models import LlmCredential
from app.transforms import service as transforms_service
from app.transforms.dispatcher import OperationError, OperationResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.data.storage import LocalFileStorage


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


_SYSTEM_TEMPLATE = """\
Eres EL data scientist senior del usuario dentro de dataprep.
El usuario NO es técnico — es un jefe de área, analista de negocio, u operación.
El usuario solo aporta **contexto del negocio** ("voy a entrenar un modelo de
churn", "esto va a un chatbot de atención al cliente"). TÚ haces el trabajo
técnico: decides el pipeline, eliges los criterios, ejecutas las
transformaciones, reportas los resultados con gráficos.

Dataset actual: **{dataset_name}**.
Origen: {source_kind} — "{source_name}".

Esquema (columnas que existen en este dataset):
{schema}

{profile_section}

REGLA #0 — NUNCA INVENTES QUE HICISTE ALGO QUE NO HICISTE

Esta es la regla más importante. Si la rompes, el usuario pierde la confianza
en la plataforma para siempre.

- Las únicas acciones que SÍ puedes ejecutar son las tools que tienes
  disponibles: ``inspect_column``, ``preview_duplicates``, ``dedupe``,
  ``fillna``, ``normalize_text``, ``parse_dates``, ``normalize_numeric``.
- Si una acción NO está en esa lista, **NO LA EJECUTASTE**. No digas
  "limpié los duplicados" si no llamaste a ``dedupe``. No digas "rellené
  los nulos" si no llamaste a ``fillna``. No digas "normalicé el texto"
  si no llamaste a ``normalize_text``. El usuario verá un badge debajo de
  cada respuesta tuya con las tools que efectivamente llamaste — si
  mientes, se nota inmediatamente.
- LO QUE NO PUEDES HACER TODAVÍA (no lo digas como si lo hubieras hecho):
  * Entrenar un modelo de ML (XGBoost, regresión, redes, etc.).
  * Evaluar un modelo (precision, recall, F1, AUC, matriz de confusión).
  * Calcular importancia de variables / SHAP / coeficientes.
  * Desplegar nada.
  * Exportar el dataset a un archivo nuevo.
  * Hacer joins, group-bys, ventanas, splits train/test.
- Cuando el usuario pida algo de la lista anterior, sé honesto: "Eso
  todavía no está habilitado en dataprep. Lo que sí puedo hacer es
  prepararte los datos perfectamente y darte una recomendación concreta
  del modelo a usar — luego tú lo entrenas en tu herramienta favorita
  (Jupyter, scikit-learn, Vertex, SageMaker, etc.)".
- Tus visualizaciones son las que producen las tools. Si no ejecutaste
  ninguna tool, no hay visualización. Acepta el hecho — no improvises
  números, métricas o gráficos en texto.

REGLA #1 — TOMA LA INICIATIVA, NO PREGUNTES NIMIEDADES TÉCNICAS

NUNCA preguntes al usuario cosas como:
- "¿Qué criterio uso para deduplicar?" — decide tú (lo obvio: dedupe por
  email/id único con keep="first" y normalize_text=True).
- "¿Qué hago con los nulos?" — decide tú (mediana en numéricas, moda en
  categóricas; solo drop_row si > 50% de la fila es null).
- "¿Qué columnas normalizo?" — decide tú a partir del esquema y el análisis.
- "¿Qué formato de fecha quieres?" — convierte a datetime nativo; el usuario
  no entiende strftime.

Solo pregunta cuando:
- El usuario no haya dado contexto del objetivo (entonces pregunta el OBJETIVO,
  no el método).
- Una decisión sea irreversible y costosa (eliminar > 30% del dataset, fusionar
  columnas semánticamente distintas).
- Haya ambigüedad real en QUÉ columna es la objetivo / target para un modelo.

REGLA #2 — EJECUTA EL PLAN COMPLETO EN UN SOLO TURNO

Cuando el usuario te da contexto, ejecuta TODO el pipeline necesario en este
mismo turno. Llama las tools en secuencia. No te detengas a preguntar entre
pasos. Cada herramienta tiene un default sensato, úsalo.

Pipeline típico para "entrenar un modelo":
1. ``inspect_column`` en las columnas con más nulos o más sospechosas
2. ``dedupe`` si hay una columna identificadora natural (email, id)
3. ``normalize_text`` en columnas de texto con casing inconsistente
4. ``parse_dates`` en columnas de fecha tipo texto
5. ``normalize_numeric`` en columnas que deberían ser número pero llegaron como texto
6. ``fillna`` con strategy='auto' para cerrar nulos restantes

Pipeline típico para "chatbot / RAG": menos limpieza, foco en la columna de
texto principal → ``normalize_text`` + ``fillna`` para esa columna.

Pipeline típico para "solo explorar": ``inspect_column`` en las 4-5 más
relevantes, luego resume hallazgos.

REGLA #3 — MUESTRA GRÁFICOS A MEDIDA QUE TRABAJAS

Cada tool produce automáticamente una visualización inline en el chat
(histograma, donut de nulos, barras antes/después, etc.). El usuario las ve
sin que tengas que pedir nada. Llama las tools generosamente al analizar —
los gráficos son cómo el usuario entiende qué encontraste.

REGLA #4 — AL TERMINAR, RESUME + RECOMIENDA EL SIGUIENTE PASO

Cuando hayas ejecutado todo el pipeline, cierra con UN mensaje claro en
lenguaje de negocio — bullets cortos, sin jerga técnica — explicando QUÉ
hiciste y POR QUÉ (en términos del objetivo del usuario, no del método).

Y dependiendo del objetivo, agrega una sección final con tu recomendación:

  - Si el objetivo era **entrenar un modelo**:
    PRIMERO sé claro: **dataprep todavía NO entrena modelos**. Lo que
    acabas de hacer es dejar los datos en condiciones óptimas para que
    el usuario los entrene fuera (en Jupyter, scikit-learn, Vertex,
    SageMaker, lo que use). Dilo explícitamente en una frase breve.

    Luego recomienda **EL modelo concreto** que usarías sobre estos
    datos, con UNA-DOS frases del por qué. Considera:
      * Tipo de columna objetivo: categórica → clasificación; numérica
        continua → regresión; serie temporal → forecast.
      * Tamaño del dataset: < 10k filas suele favorecer modelos clásicos
        (regresión logística, gradient boosting tipo XGBoost/LightGBM);
        decenas/cientos de miles → modelos más expresivos.
      * Balance de clases en clasificación: muy desbalanceado → menciona
        que conviene usar SMOTE o ``class_weight="balanced"``.
      * Interpretabilidad: si el usuario está en un contexto regulado
        (banca, salud), prioriza modelos explicables (logística, árboles
        boosteados con SHAP) sobre redes neuronales.
    Formato sugerido:
      "Listo. Los datos quedaron listos para entrenamiento.
      Recuerda que el entrenamiento del modelo en sí todavía no está
      habilitado dentro de dataprep — cuando lo conectes a tu Jupyter
      / scikit-learn / Vertex, mi recomendación es:

      **Gradient Boosting (XGBoost o LightGBM)** — buen rendimiento sin
      red neuronal, robusto a outliers, maneja bien las categóricas
      que ya quedaron codificadas."

    **NO** afirmes que "el modelo está configurado y evaluado", que
    calculaste precision/recall/F1, ni que sabes la importancia de
    variables. Esa información NO existe — la inventarías. Si el
    usuario pregunta por métricas, di que las verá cuando entrene el
    modelo en su herramienta de ML.

  - Si el objetivo era **limpiar / ajustar los datos** (sin foco en ML):
    Describe cómo dejaste la tabla aplicando las **mejores prácticas**:
      * Una fila = una observación.
      * Columnas con tipos correctos (fechas como fechas, números como
        números).
      * Sin duplicados, sin nulos sin tratar.
      * Texto normalizado.
      * Nombres de columnas consistentes.
    Y explica brevemente por qué cada criterio importa para el caso de
    uso del usuario (chatbot, reportes, dashboards, exploración).

  - Si el objetivo era **chatbot / RAG**:
    Recomienda cómo formatear el resultado como contexto: qué columna(s)
    contienen el texto principal, cuáles van como metadatos para filtrar,
    y cuál sería un tamaño de chunk razonable.

  - Si el objetivo era **solo explorar**:
    Resume los 3-4 hallazgos más interesantes y sugiere qué columna
    explorar a continuación.

Y termina SIEMPRE con SUGGESTIONS para los siguientes pasos lógicos:

SUGGESTIONS:["Ver los datos finales", "Deshacer un cambio", "Hacer ajustes", "Promover a dataset final"]

ESTILO

- Idioma: español por defecto, o el que use el usuario.
- Frases cortas. Bullets cuando enumeres.
- Cita columnas entre comillas: "categoría", "email".
- Habla en lenguaje de negocio — no menciones polars, pandas, dtypes, SQL,
  ni nombres internos de tools. El usuario no debe ver "ejecutando
  normalize_text" — debe ver "Estoy normalizando los nombres de país."
- No inventes datos que no veas en el esquema o el análisis.

PROTOCOLO DE BOTONES (SUGGESTIONS)

Cuando termines un mensaje pidiendo decisión cerrada, agrega UNA línea final:

SUGGESTIONS:["Opción 1", "Opción 2", "Otra cosa…"]

- 2 a 4 opciones, máximo ~7 palabras cada una.
- "Otra cosa…" como salida abierta cuando aplique.
- NO la incluyas en respuestas puramente informativas.

CUANDO INICIES LA CONVERSACIÓN (primer mensaje sin que el usuario haya dicho nada)

1. Saluda breve: "Hola, soy tu asistente."
2. Resume el dataset en UNA frase: nombre, columnas, filas si conoces row_count.
3. Si hubo análisis, lista en 2-4 bullets los problemas más relevantes.
4. Pregunta solo el OBJETIVO del usuario con estas cuatro opciones:

SUGGESTIONS:["Entrenar un modelo de IA con esto", "Usarlos en un chatbot", "Solo explorar y entender", "Otra cosa…"]

En el primer turno NO ejecutes nada todavía — necesitas el contexto del
objetivo primero. Apenas el usuario lo dé, ya en el siguiente turno ejecutas
todo el pipeline sin volver a preguntar detalles técnicos.
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


# Anthropic is the only provider with native tool-use wired in for this
# slice. The others can still chat — they just don't see the tools list
# and so will never call ``inspect_column`` / ``propose_dedupe``. We hand
# the user a graceful "ejecuta con Claude por ahora" message in the
# proxy-action path when they're not on Anthropic.
_TOOL_USE_PROVIDERS = {"anthropic"}

# Cap on how many inspect-and-respond round-trips one turn can run.
# A typical "clean this for ML training" pipeline runs ~6 tool calls
# (a few inspects + dedupe + fillna + normalize_text + parse_dates +
# normalize_numeric + the final summary turn). We allow enough headroom
# for the agent to also retry / branch on per-column inspection
# results without hitting the ceiling.
_MAX_TOOL_ITERATIONS = 12


async def _load_conversation_context(
    session: AsyncSession, conversation_id: UUID
) -> tuple[AgentConversation, Dataset, DataSource, LlmCredential, str]:
    """Common preamble for ``send_message`` and ``send_kickoff_turn``."""
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
    return convo, dataset, source, credential, api_key


async def _build_history_messages(
    session: AsyncSession, conversation_id: UUID, system_text: str
) -> list[ChatMessage]:
    """Re-hydrate the LLM message list from persisted rows.

    Assistant turns that carried tool_use blocks get their
    ``tool_calls`` payload restored. The matching ``system``-role
    rows that hold tool results are translated back into ``tool``
    turns the model expects to see.
    """
    rows = (
        (
            await session.execute(
                select(AgentMessage)
                .where(AgentMessage.conversation_id == conversation_id)
                .order_by(AgentMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    messages: list[ChatMessage] = [ChatMessage(role="system", content=system_text)]
    for m in rows:
        if m.role is AgentMessageRole.system:
            # Internal tool-result rows ride here; surface them as
            # tool turns if they carry a tool_use_id payload.
            if isinstance(m.tool_payload, dict) and "tool_use_id" in m.tool_payload:
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=m.content,
                        tool_use_id=str(m.tool_payload["tool_use_id"]),
                    )
                )
            continue
        tool_calls = None
        if isinstance(m.tool_payload, dict):
            raw_calls = m.tool_payload.get("tool_calls")
            if isinstance(raw_calls, list):
                tool_calls = raw_calls
        messages.append(ChatMessage(role=m.role.value, content=m.content, tool_calls=tool_calls))
    return messages


async def _run_inspect_tool(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    dataset_id: UUID,
    conversation_id: UUID,
    tool_call: ToolCall,
) -> tuple[str, list[dict[str, Any]]]:
    """Run a read-only inspection tool and return ``(json_payload,
    visualizations)``.

    The JSON payload goes back to the model as the tool_result; the
    visualizations get attached to the assistant message that emitted
    the call so the user sees the chart inline.
    """
    wc = await transforms_service.get_or_create_working_copy(
        session,
        storage=storage,
        tenant_id=tenant_id,
        user_id=user_id,
        dataset_id=dataset_id,
    )
    try:
        result: OperationResult = await transforms_service.run_operation(
            session,
            storage=storage,
            tenant_id=tenant_id,
            user_id=user_id,
            working_copy=wc,
            op=tool_call.name,
            args=tool_call.args,
            conversation_id=conversation_id,
        )
    except OperationError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False), []
    return (
        json.dumps(result.summary, ensure_ascii=False, default=str),
        result.visualizations,
    )


async def _run_agent_loop(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    conversation: AgentConversation,
    credential: LlmCredential,
    api_key: str,
    working_messages: list[ChatMessage],
) -> list[AgentMessage]:
    """Drive the assistant until it stops calling tools or asks for
    approval. Persists every assistant turn (and internal tool_result
    rows) along the way."""
    use_tools = credential.provider.value in _TOOL_USE_PROVIDERS
    tools_param = TOOLS if use_tools else None
    produced: list[AgentMessage] = []

    for _ in range(_MAX_TOOL_ITERATIONS):
        try:
            completion = await chat_completion(
                provider=credential.provider,
                api_key=api_key,
                base_url=credential.base_url,
                model=conversation.model,
                messages=working_messages,
                tools=tools_param,
            )
        except ProviderError:
            await session.rollback()
            raise

        cleaned_text, suggestions = _parse_suggestions(completion.text)
        tool_calls = list(completion.tool_calls)

        # Separate pending actions (user must approve) from auto-run
        # tools (we run them in this loop iteration).
        pending = [tc for tc in tool_calls if tc.name in PENDING_ACTION_TOOLS]
        auto_run = [tc for tc in tool_calls if tc.name not in PENDING_ACTION_TOOLS]

        tool_payload: dict[str, Any] | None = None
        if tool_calls:
            tool_payload = {
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "input": tc.args} for tc in tool_calls
                ]
            }
        # Pending-action messages also stash the proposal so the route
        # layer + frontend can render the approval card without
        # re-parsing the tool_calls list.
        visualizations: list[dict[str, Any]] = []
        if pending:
            tool_payload = dict(tool_payload or {})
            tool_payload["pending_actions"] = [
                {"id": tc.id, "name": tc.name, "args": tc.args} for tc in pending
            ]
            for tc in pending:
                visualizations.append(
                    {
                        "kind": "pending_action",
                        "tool_call_id": tc.id,
                        "tool_name": tc.name,
                        "args": tc.args,
                    }
                )

        assistant_msg = AgentMessage(
            conversation_id=conversation.id,
            role=AgentMessageRole.assistant,
            content=cleaned_text or "(respuesta vacía del modelo)",
            suggestions=suggestions,
            visualizations=visualizations or None,
            tool_payload=tool_payload,
            token_usage=completion.token_usage,
        )
        session.add(assistant_msg)
        await session.flush()
        produced.append(assistant_msg)

        # Pending action → stop the loop, the user has to react.
        if pending:
            return produced

        # No tool calls at all → final text answer, we're done.
        if not auto_run:
            return produced

        # Auto-run tools (inspect_column / preview_duplicates).
        # Feed the assistant's tool_use turn back into working history
        # before appending the tool results.
        working_messages.append(
            ChatMessage(
                role="assistant",
                content=cleaned_text,
                tool_calls=tool_payload["tool_calls"] if tool_payload else None,
            )
        )
        for tc in auto_run:
            tool_result_text, viz = await _run_inspect_tool(
                session,
                storage=storage,
                tenant_id=tenant_id,
                user_id=user_id,
                dataset_id=conversation.dataset_id,
                conversation_id=conversation.id,
                tool_call=tc,
            )
            # Surface the visualization on the assistant turn that
            # asked for the data — that's what the user sees.
            if viz:
                merged = list(assistant_msg.visualizations or []) + viz
                assistant_msg.visualizations = merged
            # Persist the tool result as an internal (system-role) row
            # so we can faithfully replay the conversation later.
            session.add(
                AgentMessage(
                    conversation_id=conversation.id,
                    role=AgentMessageRole.system,
                    content=tool_result_text,
                    tool_payload={"tool_use_id": tc.id},
                )
            )
            await session.flush()
            working_messages.append(
                ChatMessage(role="tool", content=tool_result_text, tool_use_id=tc.id)
            )

    # If we fell out of the loop, surface a polite "I gave up" message
    # instead of leaving the user hanging.
    fallback = AgentMessage(
        conversation_id=conversation.id,
        role=AgentMessageRole.assistant,
        content=(
            "Estoy dando muchas vueltas para resolver esto. "
            "¿Me cuentas con más detalle qué quieres hacer?"
        ),
    )
    session.add(fallback)
    await session.flush()
    produced.append(fallback)
    return produced


async def send_message(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    conversation_id: UUID,
    content: str,
) -> tuple[AgentMessage, list[AgentMessage]]:
    """Append the user message, run the agent loop, return the new
    rows. The loop persists every assistant turn (and internal tool-
    result rows) as it goes."""
    convo, dataset, source, credential, api_key = await _load_conversation_context(
        session, conversation_id
    )

    user_msg = AgentMessage(
        conversation_id=conversation_id,
        role=AgentMessageRole.user,
        content=content,
    )
    session.add(user_msg)
    await session.flush()

    system_text = await _build_system_prompt(session, dataset=dataset, source=source)
    working_messages = await _build_history_messages(session, conversation_id, system_text)

    assistants = await _run_agent_loop(
        session,
        storage=storage,
        tenant_id=tenant_id,
        user_id=user_id,
        conversation=convo,
        credential=credential,
        api_key=api_key,
        working_messages=working_messages,
    )

    if convo.title is None:
        convo.title = _derive_title(content)
        await session.flush()

    return user_msg, assistants


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
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    conversation_id: UUID,
) -> list[AgentMessage]:
    """Generate the agent's *opening* turn(s).

    The kickoff is one assistant message (greeting + diagnosis + intent
    chips). The agent shouldn't reach for tools on turn 1 — it doesn't
    yet know what the user wants — so we don't expect ``tool_calls``
    here in practice, but the loop tolerates them if it does."""
    convo, dataset, source, credential, api_key = await _load_conversation_context(
        session, conversation_id
    )
    system_text = await _build_system_prompt(session, dataset=dataset, source=source)
    working_messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system_text),
        ChatMessage(role="user", content=_KICKOFF_TRIGGER),
    ]
    assistants = await _run_agent_loop(
        session,
        storage=storage,
        tenant_id=tenant_id,
        user_id=user_id,
        conversation=convo,
        credential=credential,
        api_key=api_key,
        working_messages=working_messages,
    )
    if convo.title is None and assistants:
        first_line = next((ln for ln in assistants[0].content.splitlines() if ln.strip()), "")
        convo.title = _derive_title(first_line)
        await session.flush()
    return assistants


# ---------------------------------------------------------------------------
# Pending-action approval / rejection
# ---------------------------------------------------------------------------


# When the agent emits a ``propose_*`` tool, we save it as a pending
# action and stop. The user then either accepts (we run the matching
# mutating op and feed the result back to the agent for the next turn)
# or rejects (we feed back a "user declined" tool result so the agent
# can adjust). The mapping below ties each ``propose_*`` tool to its
# concrete operation name in :mod:`app.transforms`.
_PROPOSE_TO_OP: dict[str, str] = {
    "propose_dedupe": "dedupe",
}


class PendingActionError(AgentError):
    """The pending action doesn't exist or doesn't match the message."""


async def _find_pending_action(
    session: AsyncSession, message_id: UUID, tool_call_id: str
) -> tuple[AgentMessage, dict[str, Any]]:
    msg = (
        await session.execute(select(AgentMessage).where(AgentMessage.id == message_id))
    ).scalar_one_or_none()
    if msg is None:
        raise PendingActionError(str(message_id))
    payload = msg.tool_payload or {}
    actions = payload.get("pending_actions") if isinstance(payload, dict) else None
    if not isinstance(actions, list):
        raise PendingActionError("La tarjeta no tiene acciones pendientes.")
    match = next((a for a in actions if a.get("id") == tool_call_id), None)
    if match is None:
        raise PendingActionError("No encontré esa acción pendiente.")
    return msg, match


async def resolve_pending_action(
    session: AsyncSession,
    *,
    storage: LocalFileStorage,
    tenant_id: UUID,
    user_id: UUID,
    conversation_id: UUID,
    message_id: UUID,
    tool_call_id: str,
    accept: bool,
) -> list[AgentMessage]:
    """Accept (run the proposed op + continue the loop) or reject
    (feed a "user declined" tool result back to the agent and let it
    respond)."""
    convo, dataset, source, credential, api_key = await _load_conversation_context(
        session, conversation_id
    )
    _, action = await _find_pending_action(session, message_id, tool_call_id)

    tool_name = str(action.get("name", ""))
    tool_args: dict[str, Any] = action.get("args") or {}

    if accept:
        op_name = _PROPOSE_TO_OP.get(tool_name)
        if op_name is None:
            raise PendingActionError(f"No sé cómo ejecutar la acción '{tool_name}' todavía.")
        wc = await transforms_service.get_or_create_working_copy(
            session,
            storage=storage,
            tenant_id=tenant_id,
            user_id=user_id,
            dataset_id=convo.dataset_id,
        )
        try:
            result = await transforms_service.run_operation(
                session,
                storage=storage,
                tenant_id=tenant_id,
                user_id=user_id,
                working_copy=wc,
                op=op_name,
                args=tool_args,
                conversation_id=conversation_id,
                message_id=message_id,
            )
        except OperationError as e:
            result_text = json.dumps({"error": str(e), "accepted": True}, ensure_ascii=False)
            executed_visuals: list[dict[str, Any]] = []
        else:
            result_text = json.dumps(
                {"accepted": True, **result.summary},
                ensure_ascii=False,
                default=str,
            )
            executed_visuals = list(result.visualizations)
    else:
        result_text = json.dumps(
            {"accepted": False, "reason": "El usuario rechazó la acción."},
            ensure_ascii=False,
        )
        executed_visuals = []

    # Internal tool-result row so we can replay this turn faithfully.
    session.add(
        AgentMessage(
            conversation_id=conversation_id,
            role=AgentMessageRole.system,
            content=result_text,
            tool_payload={"tool_use_id": tool_call_id, "resolved_via_user": True},
        )
    )
    await session.flush()

    # Re-run the agent loop so the model can react to the result.
    system_text = await _build_system_prompt(session, dataset=dataset, source=source)
    working_messages = await _build_history_messages(session, conversation_id, system_text)
    follow_ups = await _run_agent_loop(
        session,
        storage=storage,
        tenant_id=tenant_id,
        user_id=user_id,
        conversation=convo,
        credential=credential,
        api_key=api_key,
        working_messages=working_messages,
    )

    # If the op produced visuals (e.g., before/after bar), pin them to
    # the agent's response so the user sees the result inline.
    if executed_visuals and follow_ups:
        merged = list(follow_ups[0].visualizations or []) + executed_visuals
        follow_ups[0].visualizations = merged
        await session.flush()

    return follow_ups


def _derive_title(text: str) -> str:
    one_line = " ".join(text.split())
    return one_line[:80]


__all__ = [
    "AgentError",
    "ConversationNotFoundError",
    "CredentialNotUsableError",
    "DatasetNotVisibleError",
    "PendingActionError",
    "create_conversation",
    "get_conversation",
    "get_conversation_with_messages",
    "list_conversations_for_dataset",
    "list_usable_credentials",
    "resolve_pending_action",
    "send_kickoff_turn",
    "send_message",
]
