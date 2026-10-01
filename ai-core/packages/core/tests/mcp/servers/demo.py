"""Servidor MCP de demonstração, feito com o próprio SDK: a conformidade dos transportes reais roda contra ele.

Exposto por Streamable HTTP (`http_app`), HTTP+SSE (`sse_app`) e `stdio` (executando este arquivo).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

server = MCPServer(name="demo", log_level="WARNING")


@server.tool()
def ecoar(texto: str) -> str:
    """Devolve o texto recebido."""
    return texto


@server.tool()
def quem(ctx: Context) -> str:
    """Devolve o cabeçalho Authorization que chegou ao servidor — vazio se nenhum."""
    headers = ctx.headers
    return str(headers.get("authorization", "")) if headers is not None else ""


@server.tool()
def assinatura(ctx: Context) -> str:
    """SHA-256 do cabeçalho Authorization — prova que o segredo chegou sem devolvê-lo na resposta."""
    headers = ctx.headers
    return hashlib.sha256(str(headers.get("authorization", "") if headers is not None else "").encode()).hexdigest()


@server.tool()
def ambiente(nome: str) -> str:
    """Devolve uma variável do ambiente do processo (no stdio, o do filho)."""
    return os.environ.get(nome, "")


@server.tool()
def grande(n: int) -> str:
    """Texto de n bytes."""
    return "x" * n


@server.tool()
async def lento(segundos: float) -> str:
    """Dorme e responde."""
    await asyncio.sleep(segundos)
    return "acordei"


@server.tool()
def falha() -> str:
    """Sempre falha — com `ToolError`, que o SDK repassa; exceção inesperada ele esconde do cliente."""
    raise ToolError("falha programada")


@server.tool(structured_output=False)
def imagem() -> Any:
    """Uma parte não textual."""
    from mcp_types import ImageContent

    return [ImageContent(type="image", data="aGVsbG8=", mime_type="image/png")]


def _numbered(name: str) -> Any:
    def tool() -> str:
        return name

    return tool


for _i in range(1, 51):
    server.add_tool(_numbered(f"t{_i:02d}"), name=f"t{_i:02d}", description=f"tool número {_i}")


def http_app() -> Any:
    # As suítes chegam por nomes de teste que resolvem para 127.0.0.1 (a conexão é fixada no IP, o `Host` é o nome); a
    # proteção do servidor contra DNS rebinding recusaria esses nomes. Ela é do servidor, não do cliente que testamos.
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return server.streamable_http_app(transport_security=security)


def sse_app() -> Any:
    return server.sse_app()


if __name__ == "__main__":
    asyncio.run(server.run_stdio_async())
