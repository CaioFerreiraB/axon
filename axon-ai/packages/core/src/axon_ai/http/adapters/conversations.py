"""`/conversations` nas duas superfícies (US7): o mesmo subject alcança as próprias conversas pelas duas."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response

from axon_ai.http.adapters.auth import authenticated
from axon_ai.http.domain.conversations import conversation_json, page_size
from axon_ai.http.service import ConversationService


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

    @router.get("/conversations/{conversation_id}/attachments/{attachment_id}")
    async def attachment(request: Request, conversation_id: str, attachment_id: str) -> Response:
        """Os bytes de uma imagem da conversa (ADR-044, item 9): mesma autenticação e mesmo 404 das mensagens."""
        principal = await authenticated(request, surface)
        image = await service(request).attachment(principal, conversation_id, attachment_id)
        return Response(
            content=image.data,
            media_type=image.mime,
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.delete("/conversations/{conversation_id}", status_code=204)
    async def remove(request: Request, conversation_id: str) -> Response:
        principal = await authenticated(request, surface)
        await service(request).delete(principal, conversation_id)
        return Response(status_code=204)

    return router
