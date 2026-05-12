"""Provider-agnostic chat client.

We deliberately don't import the official SDKs (anthropic / openai /
google-genai / ollama). The surface we need is tiny — *send a list
of messages, get back a string and a token count* — and the SDKs each
drag their own auth/retry/transport. Going via ``httpx`` keeps the
dependency tree small and the failure modes uniform.

Streaming (SSE) is *not* implemented here; that's the G2.2 slice. For
now every provider gives us the full response in one shot.

What this module is responsible for
-----------------------------------

* Mapping our internal ``ChatMessage`` list to each provider's
  request body.
* Calling the provider, with a generous timeout (responses can take
  30+ seconds on big context).
* Mapping the response back to ``ChatCompletion`` — text plus a
  ``{prompt, completion, total}`` token-usage dict where the provider
  gives us one. When it doesn't, we store ``None``.
* Surfacing failures as ``ProviderError`` with a human-readable
  Spanish message; the route layer maps that to HTTP 502.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.llm.models import LlmProviderKind


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One turn in the prompt we send to the provider.

    ``role`` matches the same enum the DB stores; ``content`` is plain
    text. We deliberately don't model tool-use messages here yet —
    they land in G2.3 where each provider needs a slightly different
    serialisation.
    """

    role: str  # 'system' / 'user' / 'assistant'
    content: str


@dataclass(frozen=True, slots=True)
class ChatCompletion:
    text: str
    # ``{prompt, completion, total}`` — keys are stable; values can be
    # ``None`` if the provider didn't return them. Anthropic and
    # OpenAI always do; Ollama does in recent versions; Google did not
    # until recently and we tolerate ``None`` rather than guessing.
    token_usage: dict[str, int] | None


class ProviderError(Exception):
    """Anything that went wrong calling the provider."""


# The agent loop can wait — we deliberately set a long timeout so a
# slow flagship model doesn't appear as "Network error" in the UI.
_CHAT_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


# ---------------------------------------------------------------------------
# Anthropic — POST /v1/messages
# ---------------------------------------------------------------------------


async def _chat_anthropic(
    *,
    api_key: str,
    model: str,
    messages: list[ChatMessage],
) -> ChatCompletion:
    """Anthropic separates the system prompt from the message list."""
    system_text = "\n\n".join(m.content for m in messages if m.role == "system")
    body_messages = [
        {"role": m.role, "content": m.content} for m in messages if m.role in ("user", "assistant")
    ]
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 2048,
        "messages": body_messages,
    }
    if system_text:
        payload["system"] = system_text
    async with httpx.AsyncClient(timeout=_CHAT_TIMEOUT) as client:
        try:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"No se pudo contactar al proveedor: {e}") from e
    if r.status_code >= 400:
        raise ProviderError(f"Anthropic {r.status_code}: {r.text[:300]}")
    data = r.json()
    # ``content`` is a list of {type, text}. For G2.1 we only ever ask
    # for text so concatenating the first text block is safe.
    parts = data.get("content") or []
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    usage = data.get("usage") or {}
    return ChatCompletion(
        text=text,
        token_usage={
            "prompt": int(usage.get("input_tokens", 0)),
            "completion": int(usage.get("output_tokens", 0)),
            "total": int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0)),
        }
        if usage
        else None,
    )


# ---------------------------------------------------------------------------
# OpenAI — POST /v1/chat/completions
# ---------------------------------------------------------------------------


async def _chat_openai(
    *,
    api_key: str,
    model: str,
    messages: list[ChatMessage],
) -> ChatCompletion:
    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }
    async with httpx.AsyncClient(timeout=_CHAT_TIMEOUT) as client:
        try:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"No se pudo contactar al proveedor: {e}") from e
    if r.status_code >= 400:
        raise ProviderError(f"OpenAI {r.status_code}: {r.text[:300]}")
    data = r.json()
    choices = data.get("choices") or []
    text = (choices[0].get("message", {}).get("content") or "") if choices else ""
    usage = data.get("usage") or {}
    return ChatCompletion(
        text=text,
        token_usage={
            "prompt": int(usage.get("prompt_tokens", 0)),
            "completion": int(usage.get("completion_tokens", 0)),
            "total": int(usage.get("total_tokens", 0)),
        }
        if usage
        else None,
    )


# ---------------------------------------------------------------------------
# Google — POST /v1beta/models/{model}:generateContent
# ---------------------------------------------------------------------------


async def _chat_google(
    *,
    api_key: str,
    model: str,
    messages: list[ChatMessage],
) -> ChatCompletion:
    """Google's prompt format is different enough to deserve its own
    serialiser. System messages go into a ``systemInstruction`` block;
    user/assistant turns get role-mapped (``assistant`` → ``model``)."""
    system_text = "\n\n".join(m.content for m in messages if m.role == "system")
    contents: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            continue
        role = "model" if m.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m.content}]})
    payload: dict[str, Any] = {"contents": contents}
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    async with httpx.AsyncClient(timeout=_CHAT_TIMEOUT) as client:
        try:
            r = await client.post(url, params={"key": api_key}, json=payload)
        except httpx.HTTPError as e:
            raise ProviderError(f"No se pudo contactar al proveedor: {e}") from e
    if r.status_code >= 400:
        raise ProviderError(f"Google {r.status_code}: {r.text[:300]}")
    data = r.json()
    candidates = data.get("candidates") or []
    text = ""
    if candidates:
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
    meta = data.get("usageMetadata") or {}
    usage = None
    if meta:
        usage = {
            "prompt": int(meta.get("promptTokenCount", 0)),
            "completion": int(meta.get("candidatesTokenCount", 0)),
            "total": int(meta.get("totalTokenCount", 0)),
        }
    return ChatCompletion(text=text, token_usage=usage)


# ---------------------------------------------------------------------------
# Ollama — POST /api/chat
# ---------------------------------------------------------------------------


async def _chat_ollama(
    *,
    base_url: str,
    model: str,
    messages: list[ChatMessage],
) -> ChatCompletion:
    if not base_url:
        raise ProviderError("Falta la URL del servidor Ollama.")
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }
    url = base_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=_CHAT_TIMEOUT) as client:
        try:
            r = await client.post(url, json=payload)
        except httpx.HTTPError as e:
            raise ProviderError(f"No se pudo contactar al proveedor: {e}") from e
    if r.status_code >= 400:
        raise ProviderError(f"Ollama {r.status_code}: {r.text[:300]}")
    data = r.json()
    text = (data.get("message") or {}).get("content") or ""
    # Ollama returns prompt_eval_count / eval_count (tokens). Newer
    # builds report them reliably; older ones may not.
    prompt_t = data.get("prompt_eval_count")
    completion_t = data.get("eval_count")
    usage = None
    if isinstance(prompt_t, int) and isinstance(completion_t, int):
        usage = {
            "prompt": prompt_t,
            "completion": completion_t,
            "total": prompt_t + completion_t,
        }
    return ChatCompletion(text=text, token_usage=usage)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def chat_completion(
    *,
    provider: LlmProviderKind,
    api_key: str,
    base_url: str | None,
    model: str,
    messages: list[ChatMessage],
) -> ChatCompletion:
    """Dispatch to the per-provider implementation.

    The caller has already decrypted the API key; we never persist it
    or log it here.
    """
    if provider is LlmProviderKind.anthropic:
        return await _chat_anthropic(api_key=api_key, model=model, messages=messages)
    if provider is LlmProviderKind.openai:
        return await _chat_openai(api_key=api_key, model=model, messages=messages)
    if provider is LlmProviderKind.google:
        return await _chat_google(api_key=api_key, model=model, messages=messages)
    if provider is LlmProviderKind.ollama:
        return await _chat_ollama(base_url=base_url or "", model=model, messages=messages)
    raise ProviderError(f"Proveedor no soportado: {provider}")  # pragma: no cover


__all__ = ["ChatCompletion", "ChatMessage", "ProviderError", "chat_completion"]
