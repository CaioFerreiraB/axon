"""Tradução de exceções em respostas HTTP: o envelope e o status vêm de `domain/errors.py`.

Registrado uma vez na app: as rotas levantam as exceções dos seams (003, 005) ou as do domínio, e nenhuma delas
escolhe status.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from axon_ai.assistants.api import (
    AssistantUnavailable,
    Conflict,
    NotFound,
    RateLimited,
    RequestRejected,
)
from axon_ai.graph.api import ExecutionRequestInvalid
from axon_ai.http.domain.errors import ErrorResponse, InvalidRequest, Overloaded, RequestTooLarge, error_for
from axon_ai.mcp.api import UnknownServer


class ApiError(Exception):
    """Resposta de erro já decidida (401, corpo que não é JSON) que a rota levanta."""

    def __init__(self, response: ErrorResponse) -> None:
        super().__init__(response.message)
        self.response = response


def respond(response: ErrorResponse, *, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=response.status, content=response.body(), headers={**response.headers(), **(headers or {})}
    )


async def _api_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ApiError)
    return respond(error.response)


async def _known(_request: Request, error: Exception) -> JSONResponse:
    response = error_for(error)
    if response is None:  # pragma: no cover — só registramos tipos que a tabela conhece
        raise error
    return respond(response)


def install(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    for kind in (
        NotFound,
        RequestRejected,
        InvalidRequest,
        ExecutionRequestInvalid,
        Conflict,
        AssistantUnavailable,
        RateLimited,
        UnknownServer,
        Overloaded,
        RequestTooLarge,
    ):
        app.add_exception_handler(kind, _known)
