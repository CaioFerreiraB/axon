"""`GET /models` nas duas superfícies (US2): a descoberta da 003, no formato da OpenAI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from axon_ai.assistants.api import PRIVATE_SURFACE, AssistantDirectory
from axon_ai.http.adapters.auth import authenticated
from axon_ai.http.domain.models import model_list
from axon_ai.http.ports import Clock
from axon_ai.mcp.api import McpRegistry


def models_router(*, surface: str) -> APIRouter:
    router = APIRouter()

    @router.get("/models")
    async def models(request: Request) -> Any:
        principal = await authenticated(request, surface)
        directory: AssistantDirectory = request.app.state.directory
        clock: Clock = request.app.state.clock
        result = model_list(await directory.discover(principal), owner=principal.subject, created=clock.now())
        registry: McpRegistry | None = request.app.state.mcp
        if registry is not None and surface == PRIVATE_SURFACE:
            for entry in result["data"]:
                grant = await request.app.state.grants.resolve(model=entry["id"], principal=principal)
                descriptor = await registry.delegation_for(grant)
                if descriptor is not None:
                    entry["x_axon"]["mcp_delegation"] = {
                        "version": descriptor.version,
                        "alias": descriptor.alias,
                        "endpoint": descriptor.endpoint,
                    }
        return result

    return router
