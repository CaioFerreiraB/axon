"""`GET /models` nas duas superfícies (US2): a descoberta da 003, no formato da OpenAI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ai_core.assistants.api import AssistantDirectory
from ai_core.http.adapters.auth import authenticated
from ai_core.http.domain.models import model_list
from ai_core.http.ports import Clock


def models_router(*, surface: str) -> APIRouter:
    router = APIRouter()

    @router.get("/models")
    async def models(request: Request) -> Any:
        principal = await authenticated(request, surface)
        directory: AssistantDirectory = request.app.state.directory
        clock: Clock = request.app.state.clock
        return model_list(await directory.discover(principal), owner=principal.subject, created=clock.now())

    return router
