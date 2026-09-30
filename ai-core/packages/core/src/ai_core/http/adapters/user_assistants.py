"""CRUD de Assistants de usuário, só na superfície pública (US4, FR-006). As rotas mapeiam JSON e chamam o seam."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response

from ai_core.assistants.api import PUBLIC_SURFACE, AssistantDirectory
from ai_core.http.adapters.auth import authenticated
from ai_core.http.adapters.chat import json_body
from ai_core.http.domain.assistant_body import draft_from_json, user_assistant_json


def user_assistants_router() -> APIRouter:
    router = APIRouter()

    def directory(request: Request) -> AssistantDirectory:
        return request.app.state.directory  # type: ignore[no-any-return]

    @router.get("/assistants")
    async def mine(request: Request) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        return {"data": [user_assistant_json(a) for a in await directory(request).mine(principal)]}

    @router.post("/assistants", status_code=201)
    async def create(request: Request) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        draft = draft_from_json(await json_body(request))
        return user_assistant_json(await directory(request).create(principal, draft))

    @router.get("/assistants/{name}")
    async def read(request: Request, name: str) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        return user_assistant_json(await directory(request).get(principal, name))

    @router.put("/assistants/{name}")
    async def update(request: Request, name: str) -> Any:
        principal = await authenticated(request, PUBLIC_SURFACE)
        draft = draft_from_json(await json_body(request), name=name)
        return user_assistant_json(await directory(request).update(principal, name, draft))

    @router.delete("/assistants/{name}", status_code=204)
    async def remove(request: Request, name: str) -> Response:
        principal = await authenticated(request, PUBLIC_SURFACE)
        await directory(request).delete(principal, name)
        return Response(status_code=204)

    return router
