"""Superfície privada (US5, research R20): packs e chaves para o grupo de administração, saúde para qualquer chave.

A regra de quem administra é da 003 e chega pela porta `AdminGate`; quem não administra recebe o mesmo 404 de um
recurso inexistente (clarificação de 2026-09-30).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from axon_ai.assistants.api import PRIVATE_SURFACE, ApiKeyAdmin, NotFound, Principal
from axon_ai.http.adapters.auth import authenticated
from axon_ai.http.adapters.chat import json_body
from axon_ai.http.domain.private import health_json, issue_request, key_json, packs_json
from axon_ai.http.ports import AdminGate, HealthProvider
from axon_ai.packs.api import PackRegistry


def private_router() -> APIRouter:
    router = APIRouter()

    def keys(request: Request) -> ApiKeyAdmin:
        return request.app.state.keys  # type: ignore[no-any-return]

    @router.get("/packs")
    async def packs(request: Request) -> Any:
        principal = await authenticated(request, PRIVATE_SURFACE)
        _require_admin(request, principal)
        registry: PackRegistry = request.app.state.packs
        return packs_json(registry.entries())

    @router.post("/admin/keys", status_code=201)
    async def issue(request: Request) -> Any:
        principal = await authenticated(request, PRIVATE_SURFACE)
        subject, groups, label = issue_request(await json_body(request))
        issued = await keys(request).issue(actor=principal, subject=subject, groups=groups, label=label)
        return key_json(issued.info) | {"key": issued.plaintext}

    @router.get("/admin/keys")
    async def listing(request: Request) -> Any:
        principal = await authenticated(request, PRIVATE_SURFACE)
        return {"data": [key_json(info) for info in await keys(request).keys(actor=principal)]}

    @router.delete("/admin/keys/{key_id}")
    async def revoke(request: Request, key_id: str) -> Any:
        principal = await authenticated(request, PRIVATE_SURFACE)
        return key_json(await keys(request).revoke(actor=principal, key_id=key_id))

    @router.get("/health")
    async def health(request: Request) -> Any:
        await authenticated(request, PRIVATE_SURFACE)
        provider: HealthProvider = request.app.state.health
        report = await provider.health()
        # Só item crítico tira a instância do ar: pack, Assistant ou modelo com problema é 200 `degraded` (011 FR-012).
        return JSONResponse(status_code=503 if report.status == "down" else 200, content=health_json(report))

    return router


def _require_admin(request: Request, principal: Principal) -> None:
    admin: AdminGate = request.app.state.admin
    if not admin.is_admin(principal):
        raise NotFound("recurso não encontrado")
