"""Rota de chat completions, montada nas duas superfícies.

É aqui — e só aqui — que existem status, cabeçalho e conexão. As regras de formato estão em `domain/`, e a execução,
no `service.py`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from ai_core.graph.api import ExecutionRequestInvalid
from ai_core.http.adapters.sse import MEDIA_TYPE, event_stream
from ai_core.http.domain.chat_request import ChatRequestInvalid, parse
from ai_core.http.ports import AssistantNotFound, Authenticator, Principal
from ai_core.http.service import ChatService

REQUEST_ID_HEADER = "X-Request-Id"
NOT_FOUND_DETAIL = "assistant não encontrado"
"""Mesmo texto para inexistente e para não autorizado: a existência de um Assistant privado não vaza (FR-009)."""


def chat_router(*, surface: str) -> APIRouter:
    """Roteador de uma superfície. O serviço e o autenticador vêm do estado da app, montado pela 011."""
    router = APIRouter()

    @router.post("/chat/completions")
    async def chat_completions(
        request: Request,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> Any:
        service: ChatService = request.app.state.chat_service
        authenticator: Authenticator = request.app.state.authenticator

        principal = await authenticator.authenticate(surface=surface, credential=authorization)
        if principal is None:
            raise HTTPException(status_code=401, detail="credencial inválida")

        body = await _body(request)
        try:
            chat_request = parse(body)
        except ChatRequestInvalid as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        if chat_request.stream:
            return await _stream(service, chat_request, principal)
        return await _complete(service, chat_request, principal, response)

    return router


async def _body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception as error:
        raise HTTPException(status_code=400, detail="corpo precisa ser JSON") from error
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="corpo precisa ser um objeto JSON")
    return body


async def _stream(service: ChatService, chat_request: Any, principal: Principal) -> StreamingResponse:
    """O primeiro chunk é buscado antes de responder: é o que permite 404 e 400 saírem como status, não como stream."""
    chunks = service.stream(chat_request, principal)
    try:
        first = await anext(chunks)
    except AssistantNotFound as error:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from error
    except ExecutionRequestInvalid as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    request_id = _request_id(first)
    return StreamingResponse(
        event_stream(_prepend(first, chunks)),
        media_type=MEDIA_TYPE,
        headers={REQUEST_ID_HEADER: request_id},
    )


async def _complete(
    service: ChatService, chat_request: Any, principal: Principal, response: Response
) -> Any:
    try:
        result = await service.complete(chat_request, principal)
    except AssistantNotFound as error:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from error
    except ExecutionRequestInvalid as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    headers = {REQUEST_ID_HEADER: result.request_id}
    if result.failed:
        # Sem streaming ainda dá para escolher o status: 200 com marcador de erro seria degradação silenciosa.
        return JSONResponse(status_code=502, content=result.body, headers=headers)
    response.headers[REQUEST_ID_HEADER] = result.request_id
    return result.body


async def _prepend(first: dict[str, Any], rest: Any) -> Any:
    yield first
    async for chunk in rest:
        yield chunk


def _request_id(chunk: dict[str, Any]) -> str:
    return str(chunk["id"]).removeprefix("chatcmpl-")
