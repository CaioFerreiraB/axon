"""Rotas de chat, montadas nas duas superfícies.

É aqui — e só aqui — que existem status, cabeçalho e conexão. As regras de formato estão em `domain/`, a execução no
`service.py`, e os status de erro na tabela de `domain/errors.py`: esta camada só levanta.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from ai_core.assistants.api import Principal
from ai_core.http.adapters.auth import authenticated
from ai_core.http.adapters.errors import ApiError
from ai_core.http.adapters.sse import MEDIA_TYPE, event_stream
from ai_core.http.domain.chat_request import STORE_HEADER, ChatRequest, parse
from ai_core.http.domain.errors import EXTRA, InvalidRequest, error_for
from ai_core.http.domain.native_request import parse_native
from ai_core.http.service import ChatService

REQUEST_ID_HEADER = "X-Request-Id"
CONVERSATION_ID_HEADER = "X-Conversation-Id"


def chat_router(*, surface: str) -> APIRouter:
    """Roteador de uma superfície. O serviço e o autenticador vêm do estado da app, montado pela 011."""
    router = APIRouter()

    @router.post("/chat/completions")
    async def chat_completions(request: Request, response: Response) -> Any:
        """Compat OpenAI: tolera campos que ignora, recusa os de ampliação."""
        principal = await authenticated(request, surface)
        chat = parse(await json_body(request), store_header=request.headers.get(STORE_HEADER))
        return await _run(request, response, chat, principal)

    @router.post("/chat")
    async def chat_native(request: Request, response: Response) -> Any:
        """Requisição nativa: estrita, com a mesma resposta da compat (research R17)."""
        principal = await authenticated(request, surface)
        chat = parse_native(await json_body(request), store_header=request.headers.get(STORE_HEADER))
        return await _run(request, response, chat, principal)

    return router


async def _run(request: Request, response: Response, chat_request: ChatRequest, principal: Principal) -> Any:
    service: ChatService = request.app.state.chat_service
    if chat_request.stream:
        return await _stream(service, chat_request, principal)
    return await _complete(service, chat_request, principal, response)


async def json_body(request: Request) -> dict[str, Any]:
    """O corpo como objeto JSON, ou 400 no envelope."""
    try:
        body = await request.json()
    except Exception as error:
        raise ApiError(_bad_body("corpo precisa ser JSON")) from error
    if not isinstance(body, dict):
        raise ApiError(_bad_body("corpo precisa ser um objeto JSON"))
    return body


def _bad_body(message: str) -> Any:
    response = error_for(InvalidRequest(message))
    assert response is not None
    return response


async def _stream(service: ChatService, chat_request: ChatRequest, principal: Principal) -> StreamingResponse:
    """O primeiro chunk é buscado antes de responder: é o que permite 404, 400, 424 e 429 saírem como status, e não
    como stream — os erros de resolução atravessam até os tratadores da app."""
    chunks = service.stream(chat_request, principal)
    first = await anext(chunks)
    headers = {REQUEST_ID_HEADER: _request_id(first)}
    conversation_id = first.get(EXTRA, {}).get("conversation_id")
    if conversation_id is not None:
        headers[CONVERSATION_ID_HEADER] = conversation_id
    return StreamingResponse(event_stream(_prepend(first, chunks)), media_type=MEDIA_TYPE, headers=headers)


NO_RETRY: Final = {"x-should-retry": "false"}
"""Cabeçalho que o SDK oficial da OpenAI obedece para não repetir uma resposta (research R31)."""


async def _complete(service: ChatService, chat_request: ChatRequest, principal: Principal, response: Response) -> Any:
    result = await service.complete(chat_request, principal)
    headers = {REQUEST_ID_HEADER: result.request_id}
    if result.conversation_id is not None:  # o pedido efêmero não tem conversa (FR-023)
        headers[CONVERSATION_ID_HEADER] = result.conversation_id
    if result.failed:
        # Sem streaming ainda dá para escolher o status: 200 com marcador de erro seria degradação silenciosa. E o SDK
        # oficial repete 5xx sozinho — cada repetição rodaria a execução de novo, inclusive tools de escrita (FR-022).
        return JSONResponse(status_code=502, content=result.body, headers=headers | NO_RETRY)
    response.headers.update(headers)
    return result.body


async def _prepend(first: dict[str, Any], rest: Any) -> Any:
    yield first
    async for chunk in rest:
        yield chunk


def _request_id(chunk: dict[str, Any]) -> str:
    return str(chunk["id"]).removeprefix("chatcmpl-")
