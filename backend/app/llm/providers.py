"""Provider catalogue + test_connection probes.

Each provider has:

* a default model picked when the admin doesn't specify one;
* a curated list of selectable models (so the UI shows a dropdown
  with sane choices, not whatever is in the provider's catalogue
  this week);
* a ``test_connection`` coroutine that makes a tiny, cheap request
  to verify the API key works. Each probe targets a documented,
  free-or-cheap endpoint so testing a credential doesn't burn budget.

The agent loop in ``app.agent`` calls these via a thin abstraction —
we don't import the provider SDKs here; instead each test goes
through ``httpx`` directly so we can keep the dependency surface
minimal and the failure modes uniform.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.llm.models import LlmProviderKind


@dataclass(frozen=True, slots=True)
class ModelOption:
    """One entry in the provider's model dropdown."""

    id: str
    label: str
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    """What the admin UI needs to render the 'new credential' form."""

    kind: LlmProviderKind
    display_name: str
    description: str
    # Where the admin gets their API key. Linked from the UI.
    api_key_docs_url: str
    # The form needs a base_url field only for self-hosted providers.
    needs_base_url: bool
    default_model: str
    models: list[ModelOption]


# Curated catalogues. Refreshed 2026-05; revisit when providers
# release new flagships. We list at most 4-5 options per provider so
# the dropdown stays scannable - cutting-edge first, then the cheap /
# fast tier, then the reasoning tier where it differs.
ANTHROPIC = ProviderInfo(
    kind=LlmProviderKind.anthropic,
    display_name="Claude",
    description="De Anthropic. Más natural en español; tool-use sólido.",
    api_key_docs_url="https://console.anthropic.com/settings/keys",
    needs_base_url=False,
    default_model="claude-sonnet-4-5",
    models=[
        ModelOption(
            "claude-opus-4-5",
            "Claude Opus 4.5",
            "El más potente. Recomendado para análisis complejos.",
        ),
        ModelOption(
            "claude-sonnet-4-5",
            "Claude Sonnet 4.5",
            "Balance recomendado entre potencia y costo.",
        ),
        ModelOption(
            "claude-haiku-4-5",
            "Claude Haiku 4.5",
            "Rápido y económico para tareas simples.",
        ),
    ],
)

OPENAI = ProviderInfo(
    kind=LlmProviderKind.openai,
    display_name="ChatGPT",
    description="De OpenAI. El más conocido.",
    api_key_docs_url="https://platform.openai.com/api-keys",
    needs_base_url=False,
    default_model="gpt-5",
    models=[
        ModelOption("gpt-5", "GPT-5", "El más capaz de OpenAI."),
        ModelOption("gpt-5-mini", "GPT-5 mini", "Más rápido y económico."),
        ModelOption("gpt-5-nano", "GPT-5 nano", "El más barato y rápido."),
        ModelOption("o3", "o3", "Razonamiento profundo. Lento y caro."),
        ModelOption("o4-mini", "o4-mini", "Razonamiento más económico."),
    ],
)

GOOGLE = ProviderInfo(
    kind=LlmProviderKind.google,
    display_name="Gemini",
    description="De Google. Cuota gratuita generosa al inicio.",
    api_key_docs_url="https://aistudio.google.com/app/apikey",
    needs_base_url=False,
    default_model="gemini-2.5-pro",
    models=[
        ModelOption("gemini-2.5-pro", "Gemini 2.5 Pro", "El más capaz."),
        ModelOption("gemini-2.5-flash", "Gemini 2.5 Flash", "Balance velocidad/costo."),
        ModelOption(
            "gemini-2.5-flash-lite",
            "Gemini 2.5 Flash Lite",
            "El más barato y rápido.",
        ),
    ],
)

OLLAMA = ProviderInfo(
    kind=LlmProviderKind.ollama,
    display_name="Ollama (servidor propio)",
    description="Modelo corriendo en tu propio servidor.",
    api_key_docs_url="https://ollama.com/download",
    needs_base_url=True,
    default_model="llama4:scout",
    models=[
        ModelOption(
            "llama4:scout",
            "Llama 4 Scout",
            "17B activos (MoE). Multimodal, ventana de contexto larga.",
        ),
        ModelOption(
            "llama4:maverick",
            "Llama 4 Maverick",
            "17B activos en MoE más grande. Requiere GPU potente.",
        ),
        ModelOption("qwen3:72b", "Qwen 3 72B", "Multilingüe, fuerte en código."),
        ModelOption(
            "mistral-large-2",
            "Mistral Large 2",
            "Alternativa europea. 123B parámetros.",
        ),
    ],
)


PROVIDERS: dict[LlmProviderKind, ProviderInfo] = {
    LlmProviderKind.anthropic: ANTHROPIC,
    LlmProviderKind.openai: OPENAI,
    LlmProviderKind.google: GOOGLE,
    LlmProviderKind.ollama: OLLAMA,
}


# ---------------------------------------------------------------------------
# test_connection — one cheap probe per provider
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TestResult:
    """Outcome of probing a provider with an API key.

    On success we also return the **live** list of models the key has
    access to, so the new-credential form can replace the curated
    static catalogue with whatever this specific account actually sees
    (org-restricted models, brand-new releases, etc.). When the probe
    fails we leave ``models`` empty; the UI falls back to the static
    catalogue.
    """

    ok: bool
    error: str | None = None
    models: tuple[ModelOption, ...] = ()


_TEST_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


# Per-provider filters: each provider's ``/models`` returns embeddings,
# image, speech, deprecated, etc. We only want chat-capable LLMs in the
# dropdown, so each parser filters by id / capability before returning.
def _is_openai_chat_model(model_id: str) -> bool:
    """Keep OpenAI ids that name a chat-completion-capable model."""
    if any(
        token in model_id
        for token in (
            "embedding",
            "whisper",
            "tts",
            "dall-e",
            "moderation",
            "babbage",
            "davinci-002",
            "search",
            "audio",
            "transcribe",
            "realtime",
            "image",
        )
    ):
        return False
    return (
        model_id.startswith("gpt-")
        or model_id.startswith("chatgpt")
        # ``o1``, ``o3``, ``o4-mini``, etc. — reasoning models.
        or (len(model_id) >= 2 and model_id[0] == "o" and model_id[1].isdigit())
    )


def _humanise(model_id: str) -> str:
    """Best-effort pretty label from a raw model id when the provider
    doesn't ship one. We just normalise separators and capitalise the
    leading token; the id stays visible in the option list anyway."""
    spaced = model_id.replace(":", " ").replace("-", " ").replace("_", " ")
    parts = spaced.split()
    if not parts:
        return model_id
    parts[0] = parts[0].capitalize()
    return " ".join(parts)


async def test_anthropic(api_key: str) -> TestResult:
    """``GET /v1/models`` is free and authenticates the same way as
    the messages endpoint. The response is paginated, but the default
    page is plenty for our dropdown — we only show what fits."""
    async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
        try:
            r = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
        except httpx.HTTPError as e:
            return TestResult(ok=False, error=f"Conexión: {e}")
    if r.status_code == 401:
        return TestResult(ok=False, error="Llave inválida o revocada.")
    if r.status_code >= 400:
        return TestResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:160]}")
    try:
        payload = r.json()
    except ValueError:
        return TestResult(ok=True)
    data = payload.get("data") or []
    models: list[ModelOption] = []
    for item in data:
        mid = item.get("id")
        if not isinstance(mid, str):
            continue
        # Anthropic only lists Claude family models on this endpoint,
        # so no filter needed beyond "it's actually a model".
        label = item.get("display_name") or _humanise(mid)
        models.append(ModelOption(id=mid, label=label))
    return TestResult(ok=True, models=tuple(models))


async def test_openai(api_key: str) -> TestResult:
    """``GET /v1/models`` lists everything the org can hit — embeddings,
    speech, image, deprecated, the lot. We filter to chat/reasoning."""
    async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
        try:
            r = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        except httpx.HTTPError as e:
            return TestResult(ok=False, error=f"Conexión: {e}")
    if r.status_code == 401:
        return TestResult(ok=False, error="Llave inválida o revocada.")
    if r.status_code >= 400:
        return TestResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:160]}")
    try:
        payload = r.json()
    except ValueError:
        return TestResult(ok=True)
    data = payload.get("data") or []
    models: list[ModelOption] = []
    seen: set[str] = set()
    for item in data:
        mid = item.get("id")
        if not isinstance(mid, str) or mid in seen:
            continue
        if not _is_openai_chat_model(mid):
            continue
        seen.add(mid)
        models.append(ModelOption(id=mid, label=_humanise(mid)))
    # OpenAI doesn't sort by recency; the ``created`` epoch on each
    # item does. Sort newest first so the freshest flagship is on top.
    models.sort(key=lambda m: m.id, reverse=True)
    return TestResult(ok=True, models=tuple(models))


async def test_google(api_key: str) -> TestResult:
    """``GET /v1beta/models?key=...`` — Google uses a query-string API
    key. Filters to models that support ``generateContent`` (i.e. the
    chat surface) and strips the ``models/`` URI prefix."""
    async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
        try:
            r = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key},
            )
        except httpx.HTTPError as e:
            return TestResult(ok=False, error=f"Conexión: {e}")
    if r.status_code in (401, 403):
        return TestResult(ok=False, error="Llave inválida o sin permisos.")
    if r.status_code >= 400:
        return TestResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:160]}")
    try:
        payload = r.json()
    except ValueError:
        return TestResult(ok=True)
    raw = payload.get("models") or []
    models: list[ModelOption] = []
    for item in raw:
        name = item.get("name")
        if not isinstance(name, str):
            continue
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        mid = name.removeprefix("models/")
        if "embedding" in mid or "aqa" in mid:
            continue
        label = item.get("displayName") or _humanise(mid)
        models.append(ModelOption(id=mid, label=label))
    models.sort(key=lambda m: m.id, reverse=True)
    return TestResult(ok=True, models=tuple(models))


async def test_ollama(base_url: str) -> TestResult:
    """Ollama is local — no API key. ``GET /api/tags`` lists installed
    models and doubles as a health-check endpoint."""
    if not base_url:
        return TestResult(ok=False, error="Falta la URL del servidor Ollama.")
    url = base_url.rstrip("/") + "/api/tags"
    async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
        try:
            r = await client.get(url)
        except httpx.HTTPError as e:
            return TestResult(ok=False, error=f"Conexión a Ollama: {e}")
    if r.status_code >= 400:
        return TestResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:160]}")
    try:
        payload = r.json()
    except ValueError:
        return TestResult(ok=True)
    raw = payload.get("models") or []
    models: list[ModelOption] = []
    for item in raw:
        mid = item.get("name")
        if not isinstance(mid, str):
            continue
        models.append(ModelOption(id=mid, label=_humanise(mid)))
    models.sort(key=lambda m: m.id)
    return TestResult(ok=True, models=tuple(models))


async def test_credential(
    provider: LlmProviderKind, *, api_key: str, base_url: str | None
) -> TestResult:
    """Dispatch by provider kind."""
    if provider is LlmProviderKind.anthropic:
        return await test_anthropic(api_key)
    if provider is LlmProviderKind.openai:
        return await test_openai(api_key)
    if provider is LlmProviderKind.google:
        return await test_google(api_key)
    if provider is LlmProviderKind.ollama:
        return await test_ollama(base_url or "")
    raise ValueError(f"unknown provider: {provider}")  # pragma: no cover


__all__ = [
    "ANTHROPIC",
    "GOOGLE",
    "OLLAMA",
    "OPENAI",
    "PROVIDERS",
    "ModelOption",
    "ProviderInfo",
    "TestResult",
    "test_credential",
]
