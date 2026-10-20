"""Contrato de provider de LLM (FR-013, research R21).

Provisório até a tag `contracts-v0.1.0`: o plano da 006 pode refinar estas formas no workspace, sem custo de versão.
O modelo é sempre explícito (princípio VIII) e o streaming faz parte do contrato desde o início (princípio XI).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Literal, NotRequired, Protocol, TypedDict, overload, runtime_checkable

from ai_core_contracts._freeze import JSONValue


class ChatToolCall(TypedDict):
    """Chamada de tool pedida pelo modelo; `arguments` é texto JSON, como no formato OpenAI."""

    id: str
    name: str
    arguments: str


class ChatMessage(TypedDict):
    """Mensagem enviada ao provider. Papéis: `system`, `user`, `assistant`, `tool`."""

    role: str
    content: str | None
    name: NotRequired[str]
    tool_calls: NotRequired[Sequence[ChatToolCall]]
    tool_call_id: NotRequired[str]


class ChatTool(TypedDict):
    """Tool oferecida ao modelo; o adapter do provider a traduz para o formato dele."""

    name: str
    description: str
    parameters: Mapping[str, JSONValue]


class ChatUsage(TypedDict):
    """Tokens da chamada e, quando o provider o informa (o OpenRouter informa), o custo em USD (`0.1.3`, ADR-035)."""

    prompt_tokens: int
    completion_tokens: int
    cost: NotRequired[float]


class ChatResponse(TypedDict):
    """Resposta completa (sem streaming). `message.role` é `assistant`."""

    message: ChatMessage
    finish_reason: str
    usage: NotRequired[ChatUsage]
    model: NotRequired[str]


class ChatChunk(TypedDict):
    """Pedaço de resposta em streaming. `finish_reason` e `usage` aparecem só no último."""

    delta: str
    tool_calls: NotRequired[Sequence[ChatToolCall]]
    finish_reason: NotRequired[str]
    usage: NotRequired[ChatUsage]


@runtime_checkable
class LLMProvider(Protocol):
    """Forma que os providers do core (Ollama, OpenAI, OpenRouter, simulado) cumprem. Packs não o implementam na v1."""

    @overload
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[False] = False,
    ) -> ChatResponse: ...

    @overload
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[True],
    ) -> AsyncIterator[ChatChunk]: ...
