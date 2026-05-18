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

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.llm.models import LlmProviderKind


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One turn in the prompt we send to the provider.

    For text-only turns (``role`` is ``system`` / ``user`` /
    ``assistant``), ``content`` is the body. For tool-result turns the
    ``content`` carries the JSON-stringified result and ``tool_use_id``
    points at the assistant's tool-use call this satisfies (Anthropic's
    request shape — other providers will get adapter code as they
    land). When the agent itself emits ``tool_use`` blocks, we
    represent them with ``role="assistant"`` and ``tool_calls`` set.
    """

    role: str  # 'system' / 'user' / 'assistant' / 'tool'
    content: str
    # Anthropic ``tool_use`` envelope emitted by the assistant —
    # used when we re-feed a tool-using turn back to the model.
    tool_calls: list[dict[str, Any]] | None = None
    # The id of the ``tool_use`` block this ``tool`` turn answers.
    tool_use_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool the assistant decided to call this turn."""

    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ChatCompletion:
    text: str
    # ``{prompt, completion, total}`` — keys are stable; values can be
    # ``None`` if the provider didn't return them. Anthropic and
    # OpenAI always do; Ollama does in recent versions; Google did not
    # until recently and we tolerate ``None`` rather than guessing.
    token_usage: dict[str, int] | None
    # Tools the assistant wants to call this turn. The agent service
    # walks these, runs each, and feeds the results back in a follow-
    # up turn until the assistant returns with no tool calls (a final
    # text response).
    tool_calls: tuple[ToolCall, ...] = ()
    # ``"end_turn"`` (model wrote text and is done), ``"tool_use"``
    # (model emitted tool calls, expects tool results back), or
    # whatever stop reason the provider returned. We only branch on
    # ``tool_use`` today.
    stop_reason: str | None = None


class ProviderError(Exception):
    """Anything that went wrong calling the provider."""


# The agent loop can wait — we deliberately set a long timeout so a
# slow flagship model doesn't appear as "Network error" in the UI.
_CHAT_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


# ---------------------------------------------------------------------------
# Anthropic — POST /v1/messages
# ---------------------------------------------------------------------------


def _build_anthropic_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Map our internal message list to Anthropic's wire format.

    The interesting bits:

    * Assistant turns with ``tool_calls`` set become a list of
      ``tool_use`` content blocks alongside any text, so the model
      can see its own past tool-use turn when we replay history.
    * ``tool`` turns become ``user`` messages with a single
      ``tool_result`` content block pointing at the matching
      ``tool_use_id``. (Anthropic models tool results as user turns
      by design; the role label looks weird but it's their API.)
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            continue  # system text is hoisted to the top-level ``system`` field
        if m.role == "tool" and m.tool_use_id is not None:
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_use_id,
                            "content": m.content,
                        }
                    ],
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["input"],
                    }
                )
            out.append({"role": "assistant", "content": blocks})
            continue
        out.append({"role": m.role, "content": m.content})
    return out


async def _chat_anthropic(
    *,
    api_key: str,
    model: str,
    messages: list[ChatMessage],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
) -> ChatCompletion:
    """Anthropic separates the system prompt from the message list.

    When ``tools`` is provided the model may emit ``tool_use`` blocks
    instead of (or alongside) text. We pass the blocks back as
    :class:`ToolCall` instances and let the agent service decide what
    to run.

    ``tool_choice`` follows Anthropic's wire format:
      * ``{"type": "auto"}`` — model decides (default when omitted).
      * ``{"type": "any"}`` — model MUST use one of the available tools.
        We use this to break the agent out of "I'll just describe what
        I'll do" mode on the first iteration of a follow-up turn.
      * ``{"type": "tool", "name": "..."}`` — force a specific tool.
    """
    system_text = "\n\n".join(m.content for m in messages if m.role == "system")
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 2048,
        "messages": _build_anthropic_messages(messages),
    }
    if system_text:
        payload["system"] = system_text
    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice
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
    parts = data.get("content") or []
    text_chunks: list[str] = []
    tool_calls: list[ToolCall] = []
    for p in parts:
        ptype = p.get("type")
        if ptype == "text":
            text_chunks.append(p.get("text", ""))
        elif ptype == "tool_use":
            tool_calls.append(
                ToolCall(
                    id=str(p.get("id", "")),
                    name=str(p.get("name", "")),
                    args=p.get("input") or {},
                )
            )
    usage = data.get("usage") or {}
    return ChatCompletion(
        text="".join(text_chunks),
        token_usage={
            "prompt": int(usage.get("input_tokens", 0)),
            "completion": int(usage.get("output_tokens", 0)),
            "total": int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0)),
        }
        if usage
        else None,
        tool_calls=tuple(tool_calls),
        stop_reason=data.get("stop_reason"),
    )


# ---------------------------------------------------------------------------
# OpenAI — POST /v1/chat/completions
# ---------------------------------------------------------------------------


def _build_openai_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Translate our internal message list to OpenAI's wire format.

    OpenAI differs from Anthropic in three places:

    * Tool results go as a dedicated ``role="tool"`` message with
      ``tool_call_id`` at the top level (not nested in content blocks).
    * Assistant turns with tool calls carry a top-level ``tool_calls``
      array; arguments are JSON-encoded strings, not parsed dicts.
    * System messages stay inline as a ``role="system"`` message —
      they're not hoisted to a separate field like Anthropic.
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool" and m.tool_use_id is not None:
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_use_id,
                    "content": m.content,
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                # OpenAI insists on a JSON-string here; the
                                # SDKs do the same conversion behind the scenes.
                                "arguments": json.dumps(tc.get("input") or {}),
                            },
                        }
                        for tc in m.tool_calls
                    ],
                }
            )
            continue
        out.append({"role": m.role, "content": m.content})
    return out


def _anthropic_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map our internal (Anthropic-shaped) tool specs to OpenAI's
    ``{type: 'function', function: {name, description, parameters}}``
    envelope. The JSON-Schema body inside is identical."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


def _openai_tool_choice(tool_choice: dict[str, Any] | None) -> str | dict[str, Any] | None:
    """Translate the normalized tool_choice payload to OpenAI's shape.

    Anthropic's ``{"type": "any"}`` → OpenAI's ``"required"`` (a bare
    string, not a dict — that's their API). ``{"type": "auto"}`` →
    ``"auto"``. ``{"type": "tool", "name": X}`` → the dict variant.
    """
    if tool_choice is None:
        return None
    t = tool_choice.get("type")
    if t == "any":
        return "required"
    if t == "auto":
        return "auto"
    if t == "tool":
        return {
            "type": "function",
            "function": {"name": tool_choice.get("name", "")},
        }
    return None


async def _chat_openai(
    *,
    api_key: str,
    model: str,
    messages: list[ChatMessage],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
) -> ChatCompletion:
    """OpenAI chat completion with native tool-use.

    Mirrors the Anthropic path: when ``tools`` is provided the model
    may emit ``tool_calls`` in its message; we parse them back as
    :class:`ToolCall` instances. OpenAI's ``arguments`` field is a
    JSON-encoded string — we ``json.loads`` it so the agent service
    sees a dict, identical to the Anthropic path.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": _build_openai_messages(messages),
    }
    if tools:
        payload["tools"] = _anthropic_tools_to_openai(tools)
        oc = _openai_tool_choice(tool_choice)
        if oc is not None:
            payload["tool_choice"] = oc
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
    message = choices[0].get("message", {}) if choices else {}
    text = message.get("content") or ""
    raw_tool_calls = message.get("tool_calls") or []
    tool_calls: list[ToolCall] = []
    for tc in raw_tool_calls:
        if tc.get("type") != "function":
            continue
        fn = tc.get("function") or {}
        # ``arguments`` is a JSON-encoded string on OpenAI. We parse it
        # so the agent service sees the same dict shape that Anthropic
        # delivers natively.
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args)
        except (json.JSONDecodeError, ValueError):
            args = {}
        tool_calls.append(
            ToolCall(id=str(tc.get("id", "")), name=str(fn.get("name", "")), args=args)
        )
    finish_reason = choices[0].get("finish_reason") if choices else None
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
        tool_calls=tuple(tool_calls),
        stop_reason=finish_reason,
    )


# ---------------------------------------------------------------------------
# Google — POST /v1beta/models/{model}:generateContent
# ---------------------------------------------------------------------------


def _build_google_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Translate our internal message list to Google's wire format.

    Three quirks to handle:

    * Tool results come back as ``role="user"`` messages with a
      ``functionResponse`` part containing ``{name, response}``.
      Google does NOT use a ``tool`` role.
    * Assistant turns that called tools carry ``functionCall`` parts
      *alongside* any text parts inside the same ``role="model"``
      message.
    * Anthropic-style ``assistant`` becomes ``model``; ``user`` stays.
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            continue  # hoisted into ``systemInstruction``
        if m.role == "tool" and m.tool_use_id is not None:
            # Google identifies tool results by *name* + the tool's id
            # isn't a primary key. We stash the id in the response body
            # so the model can correlate if it cares; the content is
            # the JSON we sent in OpenAI / Anthropic.
            out.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                # The tool name has to match the call; we encode
                                # it into the synthetic ``tool_use_id`` upstream
                                # by stripping the "call-" prefix some providers
                                # add. For Google we re-derive from the matching
                                # assistant turn's call name when we build
                                # messages — but practically, the agent service
                                # stores ``{tool_use_id, name}`` together when
                                # this matters. For v1 we pass the id as the
                                # name and let Google's heuristics match.
                                "name": m.tool_use_id,
                                "response": {"content": m.content},
                            }
                        }
                    ],
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            parts: list[dict[str, Any]] = []
            if m.content:
                parts.append({"text": m.content})
            for tc in m.tool_calls:
                parts.append(
                    {
                        "functionCall": {
                            "name": tc["name"],
                            "args": tc.get("input") or {},
                        }
                    }
                )
            out.append({"role": "model", "parts": parts})
            continue
        role = "model" if m.role == "assistant" else "user"
        out.append({"role": role, "parts": [{"text": m.content}]})
    return out


def _anthropic_tools_to_google(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map our tool specs to Google's nested envelope.

    Google wants ``[{"functionDeclarations": [{name, description,
    parameters}]}]`` — one outer ``tools`` entry holds all declarations.
    The JSON-Schema body is otherwise identical.
    """
    return [
        {
            "functionDeclarations": [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get(
                        "input_schema", {"type": "object", "properties": {}}
                    ),
                }
                for t in tools
            ]
        }
    ]


def _google_tool_config(tool_choice: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate the normalized tool_choice to Google's toolConfig.

    Google uses ``{"functionCallingConfig": {"mode": "ANY"|"AUTO"|"NONE"}}``
    where ``ANY`` forces a tool call (their equivalent of Anthropic's
    ``any`` / OpenAI's ``required``).
    """
    if tool_choice is None:
        return None
    t = tool_choice.get("type")
    if t == "any":
        return {"functionCallingConfig": {"mode": "ANY"}}
    if t == "auto":
        return {"functionCallingConfig": {"mode": "AUTO"}}
    if t == "tool":
        return {
            "functionCallingConfig": {
                "mode": "ANY",
                "allowedFunctionNames": [tool_choice.get("name", "")],
            }
        }
    return None


async def _chat_google(
    *,
    api_key: str,
    model: str,
    messages: list[ChatMessage],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
) -> ChatCompletion:
    """Google's prompt format is different enough to deserve its own
    serialiser. System messages go into a ``systemInstruction`` block;
    user/assistant turns get role-mapped (``assistant`` → ``model``).
    Tool calls live as ``functionCall`` parts inside model messages;
    results come back as ``functionResponse`` parts inside user
    messages.
    """
    system_text = "\n\n".join(m.content for m in messages if m.role == "system")
    payload: dict[str, Any] = {"contents": _build_google_messages(messages)}
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    if tools:
        payload["tools"] = _anthropic_tools_to_google(tools)
        cfg = _google_tool_config(tool_choice)
        if cfg is not None:
            payload["toolConfig"] = cfg
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
    text_chunks: list[str] = []
    tool_calls: list[ToolCall] = []
    if candidates:
        parts = candidates[0].get("content", {}).get("parts") or []
        for i, p in enumerate(parts):
            if "text" in p:
                text_chunks.append(p.get("text", ""))
            elif "functionCall" in p:
                fc = p["functionCall"]
                # Google doesn't ship a stable id for function calls; we
                # synthesize one from the index so we can match the
                # response back through ``functionResponse.name``.
                tool_calls.append(
                    ToolCall(
                        id=str(fc.get("name", f"call_{i}")),
                        name=str(fc.get("name", "")),
                        args=fc.get("args") or {},
                    )
                )
    finish_reason = candidates[0].get("finishReason") if candidates else None
    meta = data.get("usageMetadata") or {}
    usage = None
    if meta:
        usage = {
            "prompt": int(meta.get("promptTokenCount", 0)),
            "completion": int(meta.get("candidatesTokenCount", 0)),
            "total": int(meta.get("totalTokenCount", 0)),
        }
    return ChatCompletion(
        text="".join(text_chunks),
        token_usage=usage,
        tool_calls=tuple(tool_calls),
        stop_reason=finish_reason,
    )


# ---------------------------------------------------------------------------
# Ollama — POST /api/chat
# ---------------------------------------------------------------------------


def _build_ollama_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Ollama's ``/api/chat`` speaks an OpenAI-compatible message shape
    on recent versions: ``role`` of ``system|user|assistant|tool``, with
    tool results as ``role="tool"`` carrying ``tool_call_id``, and
    assistant turns with tool calls carrying ``tool_calls`` (arguments
    JSON-stringified). The translation is the same as OpenAI's."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool" and m.tool_use_id is not None:
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_use_id,
                    "content": m.content,
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                # Ollama (recent) accepts arguments either as
                                # a JSON string (OpenAI-style) or as a dict;
                                # we send the dict form which is friendlier
                                # to llama3.1+ and qwen2.5+.
                                "arguments": tc.get("input") or {},
                            },
                        }
                        for tc in m.tool_calls
                    ],
                }
            )
            continue
        out.append({"role": m.role, "content": m.content})
    return out


async def _chat_ollama(
    *,
    base_url: str,
    model: str,
    messages: list[ChatMessage],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
) -> ChatCompletion:
    """Ollama chat completion with native tool-use on recent versions.

    Not every Ollama model supports tools — only the function-calling
    family (``llama3.1+``, ``qwen2.5+``, ``mistral-nemo``, etc.). If
    the model doesn't recognise the ``tools`` parameter, Ollama
    silently ignores it and we fall back to a text-only response —
    the agent loop handles that gracefully.

    We don't pass ``tool_choice`` to Ollama: support is patchy across
    models and the field is silently ignored on the ones that lack
    it. We rely on the imperative system prompt to nudge tool use.
    """
    if not base_url:
        raise ProviderError("Falta la URL del servidor Ollama.")
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "messages": _build_ollama_messages(messages),
    }
    if tools:
        # Ollama uses the OpenAI tool envelope verbatim.
        payload["tools"] = _anthropic_tools_to_openai(tools)
    url = base_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=_CHAT_TIMEOUT) as client:
        try:
            r = await client.post(url, json=payload)
        except httpx.HTTPError as e:
            raise ProviderError(f"No se pudo contactar al proveedor: {e}") from e
    if r.status_code >= 400:
        raise ProviderError(f"Ollama {r.status_code}: {r.text[:300]}")
    data = r.json()
    message = data.get("message") or {}
    text = message.get("content") or ""
    raw_tool_calls = message.get("tool_calls") or []
    tool_calls: list[ToolCall] = []
    for i, tc in enumerate(raw_tool_calls):
        fn = tc.get("function") or {}
        raw_args = fn.get("arguments")
        # Recent Ollama returns args as a dict; older builds (and some
        # models) return them JSON-stringified like OpenAI. Tolerate
        # both.
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except (json.JSONDecodeError, ValueError):
                args = {}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}
        tool_calls.append(
            ToolCall(
                id=str(tc.get("id") or f"call_{i}"),
                name=str(fn.get("name", "")),
                args=args,
            )
        )
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
    return ChatCompletion(
        text=text,
        token_usage=usage,
        tool_calls=tuple(tool_calls),
        stop_reason=data.get("done_reason"),
    )


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
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
) -> ChatCompletion:
    """Dispatch to the per-provider implementation.

    The caller has already decrypted the API key; we never persist it
    or log it here.

    ``tools`` is implemented for Anthropic in this slice. The other
    providers ignore it for now — they'll get per-vendor adapters as
    the tool-use surface stabilises (each has a different request
    shape: OpenAI ``tool_calls``, Google ``functionCall`` parts,
    Ollama OpenAI-compatible tools on recent models).
    """
    if provider is LlmProviderKind.anthropic:
        return await _chat_anthropic(
            api_key=api_key,
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
    if provider is LlmProviderKind.openai:
        return await _chat_openai(
            api_key=api_key,
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
    if provider is LlmProviderKind.google:
        return await _chat_google(
            api_key=api_key,
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
    if provider is LlmProviderKind.ollama:
        return await _chat_ollama(
            base_url=base_url or "",
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
    raise ProviderError(f"Proveedor no soportado: {provider}")  # pragma: no cover


__all__ = ["ChatCompletion", "ChatMessage", "ProviderError", "chat_completion"]
