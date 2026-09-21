"""Fábrica da app HTTP, chamada pela composition root (spec 011).

As duas superfícies são o mesmo roteador montado em dois prefixos, cada um sabendo qual é a sua — é o que o
`design.md` descreve e evita duplicar rota (FR-001).
"""

from __future__ import annotations

from fastapi import FastAPI

from ai_core.graph.api import ExecutionEngine
from ai_core.http.adapters.chat import chat_router
from ai_core.http.ports import PRIVATE_SURFACE, PUBLIC_SURFACE, Authenticator, Clock, GrantResolver, RequestIds
from ai_core.http.service import ChatService

PUBLIC_PREFIX = "/v1"
PRIVATE_PREFIX = "/private/v1"


def create_app(
    *,
    engine: ExecutionEngine,
    authenticator: Authenticator,
    grants: GrantResolver,
    request_ids: RequestIds,
    clock: Clock,
) -> FastAPI:
    """Monta a app com os seams já injetados. A API não instancia nada: recebe tudo pronto (princípio XIII)."""
    app = FastAPI(title="ai-core", version="0.1.0")
    app.state.chat_service = ChatService(
        engine=engine, grants=grants, request_ids=request_ids, clock=clock
    )
    app.state.authenticator = authenticator
    app.include_router(chat_router(surface=PUBLIC_SURFACE), prefix=PUBLIC_PREFIX)
    app.include_router(chat_router(surface=PRIVATE_SURFACE), prefix=PRIVATE_PREFIX)
    return app
