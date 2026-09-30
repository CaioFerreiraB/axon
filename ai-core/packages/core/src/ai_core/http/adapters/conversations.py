"""`/conversations` nas duas superfícies (US7): o mesmo subject alcança as próprias conversas pelas duas."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response

from ai_core.http.adapters.auth import authenticated
from ai_core.http.domain.conversations import conversation_json, page_size
from ai_core.http.service import ConversationService


def conversations_router(*, surface: str) -> APIRouter:
    router = APIRouter()

    def service(request: Request) -> ConversationService:
        return request.app.state.conversation_service  # type: ignore[no-any-return]

    @router.get("/conversations")
    async def listing(request: Request) -> Any:
        principal = await authenticated(request, surface)
        limit = page_size(request.query_params.get("limit"))
        page = await service(request).page(principal, limit=limit, cursor=request.query_params.get("cursor"))
        return {"data": [conversation_json(c) for c in page.items], "next_cursor": page.next_cursor}

    @router.get("/conversations/{conversation_id}")
    async def read(request: Request, conversation_id: str) -> Any:
        principal = await authenticated(request, surface)
        conversation, messages = await service(request).read(principal, conversation_id)
        return conversation_json(conversation, messages)

    @router.delete("/conversations/{conversation_id}", status_code=204)
    async def remove(request: Request, conversation_id: str) -> Response:
        principal = await authenticated(request, surface)
        await service(request).delete(principal, conversation_id)
        return Response(status_code=204)

    return router
