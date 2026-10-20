"""O que os transportes `http`, `sse` e `stdio` têm em comum sobre o SDK de MCP: uma sessão por operação, dentro do
prazo, com os tipos do SDK traduzidos para os registros da porta e toda falha em `TransportFailure` (research R6).

O SDK só aparece em `adapters/` (import-linter).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any, Final

import anyio
import mcp_types as types
from mcp.client.session import ClientSession
from mcp.shared.exceptions import MCPError

from axon_ai.mcp.ports import OperationLimits, RemotePart, RemoteResult, RemoteTool, TransportFailure
from axon_ai_contracts import JSONValue

MAX_PAGES: Final = 20
"""`tools/list` paginado: um servidor que nunca termina a paginação não prende a descoberta."""

Streams = AbstractAsyncContextManager[Any]
"""O que um cliente do SDK devolve: o par de streams de leitura e escrita da sessão."""


Explain = Callable[[BaseException], str | None]
"""O motivo que só o transporte conhece (destino bloqueado, teto de bytes), quando a falha chega embrulhada pelo SDK."""


def _no_explanation(_error: BaseException) -> str | None:
    return None


async def list_tools(
    open_streams: Callable[[], Streams], *, limits: OperationLimits, explain: Explain = _no_explanation
) -> Sequence[RemoteTool]:
    async def operation(session: ClientSession) -> Sequence[RemoteTool]:
        tools: list[RemoteTool] = []
        cursor: str | None = None
        for _ in range(MAX_PAGES):
            params = types.PaginatedRequestParams(cursor=cursor) if cursor else None
            page = await session.list_tools(params=params)
            tools.extend(_tool(tool) for tool in page.tools)
            cursor = page.next_cursor
            if not cursor:
                break
        return tools

    return await run(open_streams, operation, limits=limits, explain=explain)


async def call_tool(
    open_streams: Callable[[], Streams],
    name: str,
    arguments: Mapping[str, JSONValue],
    *,
    limits: OperationLimits,
    explain: Explain = _no_explanation,
) -> RemoteResult:
    async def operation(session: ClientSession) -> RemoteResult:
        result = await session.call_tool(name, _plain(arguments))
        if not isinstance(result, types.CallToolResult):
            raise TransportFailure(f"resultado inesperado do servidor: {type(result).__name__}")
        return RemoteResult(
            parts=tuple(_part(item) for item in result.content),
            structured=result.structured_content,
            is_error=bool(result.is_error),
        )

    return await run(open_streams, operation, limits=limits, explain=explain)


async def run[T](
    open_streams: Callable[[], Streams],
    operation: Callable[[ClientSession], Any],
    *,
    limits: OperationLimits,
    explain: Explain = _no_explanation,
) -> T:
    """Abre a sessão, inicializa e roda a operação, tudo dentro do prazo. `explain` deixa o transporte dar o motivo
    que só ele conhece (destino bloqueado, teto de bytes) quando a falha aparece embrulhada pelo SDK."""
    try:
        with anyio.fail_after(limits.timeout):
            async with open_streams() as streams, ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result: T = await operation(session)
                return result
    except TransportFailure:
        raise
    except TimeoutError as error:
        raise TransportFailure(explain(error) or f"sem resposta em {limits.timeout:g} s") from None
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit, anyio.get_cancelled_exc_class())):
            raise
        raise TransportFailure(explain(error) or describe(error)) from None


def describe(error: BaseException) -> str:
    """A primeira causa concreta, sem o embrulho dos grupos de tarefas do SDK."""
    leaf = first_leaf(error)
    if isinstance(leaf, TransportFailure):
        return leaf.reason
    if isinstance(leaf, TimeoutError):
        return "sem resposta no prazo"
    if isinstance(leaf, MCPError):
        return f"erro do protocolo MCP: {leaf}"
    if isinstance(leaf, OSError):
        return f"falha de E/S: {leaf.strerror or type(leaf).__name__}"
    text = str(leaf).strip().splitlines()[0] if str(leaf).strip() else ""
    return f"{type(leaf).__name__}: {text}" if text else type(leaf).__name__


def first_leaf(error: BaseException) -> BaseException:
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    return error


def leaves(error: BaseException) -> list[BaseException]:
    """Todas as causas de um grupo, em profundidade."""
    if isinstance(error, BaseExceptionGroup):
        return [leaf for inner in error.exceptions for leaf in leaves(inner)]
    return [error]


def _tool(tool: types.Tool) -> RemoteTool:
    schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
    return RemoteTool(name=tool.name, description=tool.description, input_schema=schema)


def _part(item: Any) -> RemotePart:
    kind = getattr(item, "type", None) or type(item).__name__
    if kind == "text":
        return RemotePart(kind="text", text=getattr(item, "text", ""))
    return RemotePart(kind=str(kind))


def _plain(arguments: Mapping[str, JSONValue]) -> dict[str, Any]:
    """Os argumentos chegam congelados (contratos 001); o SDK serializa dicionários e listas."""

    def thaw(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: thaw(item) for key, item in value.items()}
        if isinstance(value, tuple | list):
            return [thaw(item) for item in value]
        return value

    return {key: thaw(value) for key, value in arguments.items()}
