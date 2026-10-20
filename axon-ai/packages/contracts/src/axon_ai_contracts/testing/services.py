"""Suítes mínimas dos contratos de serviço (research R21, R22; testing-kit.md).

Rodam contra os falsos na 001 e contra os adapters reais na 006 (LLMProvider) e na 007 (MCPClient), que podem
ampliá-las. Exceção levantada vira a issue da checagem correspondente, com a exceção na mensagem.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import cast

from axon_ai_contracts._freeze import JSONValue
from axon_ai_contracts.declaration import ContractIssue
from axon_ai_contracts.llm import ChatMessage, LLMProvider
from axon_ai_contracts.mcp import MCPClient
from axon_ai_contracts.tools import ToolResult, ToolSpec

_PING: tuple[ChatMessage, ...] = ({"role": "user", "content": "ping"},)


def _response_problem(response: object) -> str | None:
    if not isinstance(response, Mapping):
        return f"chat devolveu {type(response).__name__}; esperado ChatResponse"
    message = response.get("message")
    if not isinstance(message, Mapping) or message.get("role") != "assistant":
        return 'ChatResponse.message precisa ter role "assistant"'
    if not (message.get("content") is None or isinstance(message.get("content"), str)):
        return "ChatResponse.message.content precisa ser str ou None"
    if not isinstance(response.get("finish_reason"), str):
        return "ChatResponse.finish_reason precisa ser str"
    return None


def _stream_problem(chunks: Sequence[object]) -> str | None:
    if not chunks:
        return "o stream não produziu nenhum chunk"
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, Mapping) or not isinstance(chunk.get("delta"), str):
            return f"chunk {index} sem delta str"
        last = index == len(chunks) - 1
        has_finish = isinstance(chunk.get("finish_reason"), str)
        if last and not has_finish:
            return "o último chunk precisa trazer finish_reason"
        if not last and "finish_reason" in chunk:
            return f"finish_reason só pode aparecer no último chunk (apareceu no {index})"
    return None


async def acheck_llm_provider(provider: object, *, model: str = "test-model") -> tuple[ContractIssue, ...]:
    """Forma da resposta sem stream e do stream de um `LLMProvider`."""
    llm = cast("LLMProvider", provider)
    issues: list[ContractIssue] = []
    try:
        problem = _response_problem(await llm.chat(_PING, model))
    except Exception as error:
        problem = f"chat levantou {type(error).__name__}: {error}"
    if problem is not None:
        issues.append(ContractIssue(code="llm.response.invalid", message=problem, subject="llm:chat"))
    try:
        stream = await llm.chat(_PING, model, stream=True)
        chunks: list[object] = [chunk async for chunk in cast("AsyncIterator[object]", stream)]
        problem = _stream_problem(chunks)
    except Exception as error:
        problem = f"chat(stream=True) levantou {type(error).__name__}: {error}"
    if problem is not None:
        issues.append(ContractIssue(code="llm.stream.invalid", message=problem, subject="llm:chat(stream=True)"))
    return tuple(issues)


async def acheck_mcp_client(
    client: object,
    *,
    alias: str,
    tool: str,
    arguments: Mapping[str, JSONValue] | None = None,
) -> tuple[ContractIssue, ...]:
    """Descoberta devolve ToolSpec `mcp` sem handler; execução devolve ToolResult não-confiável."""
    mcp = cast("MCPClient", client)
    issues: list[ContractIssue] = []
    try:
        tools = await mcp.discover_tools([alias])
        valid = (
            isinstance(tools, Sequence)
            and not isinstance(tools, str | bytes)
            and all(isinstance(spec, ToolSpec) and spec.kind == "mcp" and spec.handler is None for spec in tools)
        )
        problem = None if valid else 'discover_tools precisa devolver ToolSpec com kind "mcp" e sem handler'
    except Exception as error:
        problem = f"discover_tools levantou {type(error).__name__}: {error}"
    if problem is not None:
        issues.append(ContractIssue(code="mcp.discovery.invalid", message=problem, subject=f"mcp:{alias}"))
    try:
        result = await mcp.execute(alias, tool, dict(arguments or {}))
        valid = isinstance(result, ToolResult) and result.untrusted is True
        problem = None if valid else "execute precisa devolver ToolResult com untrusted=True"
    except Exception as error:
        problem = f"execute levantou {type(error).__name__}: {error}"
    if problem is not None:
        issues.append(ContractIssue(code="mcp.result.invalid", message=problem, subject=f"mcp:{alias}.{tool}"))
    return tuple(issues)
