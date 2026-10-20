"""`GET /models` nas duas superfícies (US2): a descoberta da 003, no formato da OpenAI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from axon_ai.assistants.api import AssistantDirectory
from axon_ai.http.adapters.auth import authenticated
from axon_ai.http.domain.models import model_list
from axon_ai.http.ports import Clock


def models_router(*, surface: str) -> APIRouter:
    router = APIRouter()

    @router.get("/models")
    async def models(request: Request) -> Any:
        principal = await authenticated(request, surface)
        directory: AssistantDirectory = request.app.state.directory
        clock: Clock = request.app.state.clock
        return model_list(await directory.discover(principal), owner=principal.subject, created=clock.now())

    return router
