"""Rotas de MCP (Fase 3; US4, US5; contracts/mcp-routes.md): só mapeiam JSON e chamam o seam `McpRegistry` da 007.

As regras de escopo, de rede e de credencial são da 007; quem administra os globais é a regra da 003, pela porta
`AdminGate` — quem não administra recebe o mesmo 404 de recurso inexistente (research R27).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response

from ai_core.assistants.api import PRIVATE_SURFACE, PUBLIC_SURFACE, NotFound, Principal
from ai_core.http.adapters.auth import authenticated
from ai_core.http.adapters.chat import json_body
from ai_core.http.domain.mcp_body import USER_PREFIX, draft_from_json, health_json, server_json, summary_json
from ai_core.http.ports import AdminGate
from ai_core.mcp.api import McpRegistry


def _registry(request: Request) -> McpRegistry:
    return request.app.state.mcp  # type: ignore[no-any-return]


def _mine(alias: str) -> str:
    """O alias de usuário com `~` — o caminho aceita com ou sem (como os Assistants de usuário)."""
    return alias if alias.startswith(USER_PREFIX) else f"{USER_PREFIX}{alias}"


def user_mcp_router() -> APIRouter:
    """`/v1/mcp`: os servidores do próprio usuário (R26)."""
    router = APIRouter()

    @router.get("/mcp")
    async def mine(request: Request) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        return {"data": [server_json(s) for s in await _registry(request).mine(principal)]}

    @router.post("/mcp", status_code=201)
    async def create(request: Request) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        draft = draft_from_json(await json_body(request), scope="user")
        return server_json(await _registry(request).create_mine(principal, draft))

    # Rota literal antes de `{alias}`: `available` não é alias de ninguém.
    @router.get("/mcp/available")
    async def available(request: Request) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        return {"data": [summary_json(s) for s in await _registry(request).available(principal)]}

    @router.get("/mcp/{alias}")
    async def read(request: Request, alias: str) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        return server_json(await _registry(request).get_mine(principal, _mine(alias)))

    @router.put("/mcp/{alias}")
    async def update(request: Request, alias: str) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        draft = draft_from_json(await json_body(request), scope="user", alias=_mine(alias))
        return server_json(await _registry(request).update_mine(principal, _mine(alias), draft))

    @router.delete("/mcp/{alias}", status_code=204)
    async def remove(request: Request, alias: str) -> Response:
        principal = await authenticated(request, PUBLIC_SURFACE)
        await _registry(request).delete_mine(principal, _mine(alias))
        return Response(status_code=204)

    @router.get("/mcp/{alias}/health")
    async def health(request: Request, alias: str) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        registry = _registry(request)
        server = await registry.get_mine(principal, _mine(alias))  # MCP alheio é inexistente antes de sair para a rede
        return health_json(await registry.check(server.alias, owner=principal.subject))

    return router


def global_mcp_router() -> APIRouter:
    """`/private/v1/mcp`: os servidores globais, só para o grupo de administração (R27)."""
    router = APIRouter()

    async def admin(request: Request) -> Principal:
        principal = await authenticated(request, PRIVATE_SURFACE)
        gate: AdminGate = request.app.state.admin
        if not gate.is_admin(principal):
            # Quem não administra não fica sabendo que a rota existe — o 404 de recurso inexistente (R20).
            raise NotFound("recurso não encontrado")
        return principal

    @router.get("/mcp")
    async def listing(request: Request) -> Any:
        await admin(request)
        return {"data": [server_json(s) for s in await _registry(request).globals()]}

    @router.post("/mcp", status_code=201)
    async def create(request: Request) -> Any:
        await admin(request)
        draft = draft_from_json(await json_body(request), scope="global")
        return server_json(await _registry(request).create_global(draft))

    @router.get("/mcp/{alias}")
    async def read(request: Request, alias: str) -> Any:
        await admin(request)
        return server_json(await _registry(request).get_global(alias))

    @router.put("/mcp/{alias}")
    async def update(request: Request, alias: str) -> Any:
        await admin(request)
        draft = draft_from_json(await json_body(request), scope="global", alias=alias)
        return server_json(await _registry(request).update_global(alias, draft))

    @router.delete("/mcp/{alias}", status_code=204)
    async def remove(request: Request, alias: str) -> Response:
        await admin(request)
        await _registry(request).delete_global(alias)
        return Response(status_code=204)

    @router.get("/mcp/{alias}/health")
    async def health(request: Request, alias: str) -> Any:
        await admin(request)
        registry = _registry(request)
        await registry.get_global(alias)  # inexistente é 404 antes de sair para a rede
        return health_json(await registry.check(alias))

    return router
