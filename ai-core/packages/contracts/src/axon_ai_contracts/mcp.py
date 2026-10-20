"""Contrato de cliente MCP (FR-014, research R22). Provisório até a tag `contracts-v0.1.0`.

O cliente recebe só aliases já autorizados pelo grant, nunca endereços: a resolução alias → endpoint + credencial
acontece no MCP Registry (spec 007). Ponto em aberto para o plano da 007: o retorno de `discover_tools` não diz de
qual alias veio cada tool — quem precisa dessa associação chama por alias.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from axon_ai_contracts._freeze import JSONValue
from axon_ai_contracts.tools import ToolResult, ToolSpec


@runtime_checkable
class MCPClient(Protocol):
    """Forma que o cliente MCP restrito do core (007) cumpre. Tools descobertas têm `kind="mcp"` e nenhum handler."""

    async def discover_tools(self, aliases: Sequence[str]) -> Sequence[ToolSpec]: ...

    async def execute(self, alias: str, tool: str, arguments: Mapping[str, JSONValue]) -> ToolResult: ...
