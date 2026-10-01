"""`McpTransport` por `stdio` (research R6): o servidor é um processo filho, com comando, argumentos e ambiente
fixados no arquivo do operador — nunca pela API (ADR-003). Executado sem shell.

Sem teto de bytes no transporte: o servidor é do operador, e o corte do conteúdo e o prazo bastam (R6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any

from mcp.client.stdio import StdioServerParameters, stdio_client

from ai_core.mcp.adapters import sdk_session
from ai_core.mcp.ports import OperationLimits, RemoteResult, RemoteTool, Target, TransportFailure
from ai_core_contracts import JSONValue


class StdioMcpTransport:
    async def list_tools(self, target: Target, *, limits: OperationLimits) -> Sequence[RemoteTool]:
        return await sdk_session.list_tools(lambda: self._open(target), limits=limits)

    async def call_tool(
        self, target: Target, name: str, arguments: Mapping[str, JSONValue], *, limits: OperationLimits
    ) -> RemoteResult:
        return await sdk_session.call_tool(lambda: self._open(target), name, arguments, limits=limits)

    @staticmethod
    def _open(target: Target) -> AbstractAsyncContextManager[Any]:
        if target.stdio is None:
            raise TransportFailure(f"'{target.alias}' não tem comando stdio")
        command = target.stdio
        # O ambiente do filho: o do SDK (PATH, HOME…), os literais do arquivo e os segredos já resolvidos.
        environment = dict(command.env) | dict(target.environment)
        parameters = StdioServerParameters(command=command.command, args=list(command.args), env=environment)
        return stdio_client(parameters)
