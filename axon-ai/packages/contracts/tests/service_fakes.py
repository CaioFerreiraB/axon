"""Falsos dos contratos de serviço (LLMProvider, MCPClient), usados pelos testes de forma e pelas suítes mínimas."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from axon_ai_contracts import ChatChunk, ChatResponse, ToolResult, ToolSpec

DEFAULT_RESPONSE: ChatResponse = {"message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}
DEFAULT_CHUNKS: tuple[ChatChunk, ...] = ({"delta": "po"}, {"delta": "ng", "finish_reason": "stop"})
ECHO_TOOL = ToolSpec(name="echo", description="Eco.", parameters={"type": "object"}, kind="mcp")


class FakeLLMProvider:
    """Provider simulado: resposta fixa e stream de chunks fixos; `error` faz `chat` levantar."""

    def __init__(
        self,
        *,
        response: Any = DEFAULT_RESPONSE,
        chunks: Sequence[Any] = DEFAULT_CHUNKS,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.chunks = tuple(chunks)
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        model: str,
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        response_format: Mapping[str, Any] | None = None,
        stream: bool = False,
    ) -> Any:
        self.calls.append({"messages": messages, "model": model, "stream": stream})
        if self.error is not None:
            raise self.error
        if stream:
            return self._stream()
        return self.response

    async def _stream(self) -> AsyncIterator[Any]:
        for chunk in self.chunks:
            yield chunk


class FakeMCPClient:
    """Cliente MCP simulado: descobre tools fixas e devolve os argumentos como conteúdo."""

    def __init__(self, *, tools: Sequence[Any] = (ECHO_TOOL,), result: Any = None) -> None:
        self.tools = tuple(tools)
        self.result = result

    async def discover_tools(self, aliases: Sequence[str]) -> Sequence[Any]:
        return self.tools

    async def execute(self, alias: str, tool: str, arguments: Mapping[str, Any]) -> Any:
        if self.result is not None:
            return self.result
        return ToolResult(content={"alias": alias, "tool": tool, "arguments": dict(arguments)})
