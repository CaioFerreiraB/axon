"""Fábrica da app HTTP, chamada pela composition root (spec 011).

As duas superfícies são os mesmos roteadores montados em dois prefixos, cada um sabendo qual é a sua (FR-001). A de
administração (`/admin/v1`, US9) só existe quando a composition root passa os seams dela. A app
recebe tudo pronto: os seams da 003, 002 e 005 e os adapters das portas deste módulo (princípio XIII).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import timedelta

from fastapi import FastAPI

from axon_ai.assistants.api import (
    ADMIN_SURFACE,
    PRIVATE_SURFACE,
    PUBLIC_SURFACE,
    ApiKeyAdmin,
    AssistantDirectory,
    Authenticator,
    GrantResolver,
)
from axon_ai.graph.api import ExecutionEngine
from axon_ai.http.adapters import errors
from axon_ai.http.adapters.admin import ADMIN_PREFIX, AdminHeaders, admin_fallback_router, admin_router
from axon_ai.http.adapters.chat import chat_router
from axon_ai.http.adapters.conversations import conversations_router
from axon_ai.http.adapters.mcp_routes import global_mcp_router, user_mcp_router
from axon_ai.http.adapters.models import models_router
from axon_ai.http.adapters.private import private_router
from axon_ai.http.adapters.static import ChartAssets, static_router
from axon_ai.http.adapters.user_assistants import user_assistants_router
from axon_ai.http.domain.admission import AdmissionLimits as AdmissionLimits  # a 011 monta os limites (R36)
from axon_ai.http.domain.images import ImageLimits
from axon_ai.http.ports import (
    AdminGate,
    AdminSeams,
    Clock,
    ConversationStore,
    HealthProvider,
    InstanceBranding,
    RequestIds,
)
from axon_ai.http.service import DEFAULT_RETENTION, ChatService, ConversationService
from axon_ai.mcp.api import McpRegistry
from axon_ai.packs.api import PackRegistry

PUBLIC_PREFIX = "/v1"
PRIVATE_PREFIX = "/private/v1"

type Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]
"""Início e fim da app no laço do servidor. É da composition root: pool de banco e tarefas periódicas (011 R14)."""


def create_app(
    *,
    engine: ExecutionEngine,
    authenticator: Authenticator,
    grants: GrantResolver,
    directory: AssistantDirectory,
    keys: ApiKeyAdmin,
    packs: PackRegistry,
    admin: AdminGate,
    conversations: ConversationStore,
    health: HealthProvider,
    request_ids: RequestIds,
    conversation_ids: RequestIds,
    clock: Clock,
    conversation_retention: timedelta = DEFAULT_RETENTION,
    lifespan: Lifespan | None = None,
    mcp: McpRegistry | None = None,
    admission: AdmissionLimits | None = None,
    admin_seams: AdminSeams | None = None,
    instance: InstanceBranding | None = None,
    image_limits: ImageLimits | None = None,
    charts_base_url: str | None = None,
) -> FastAPI:
    """Monta a app com os seams já injetados. A API não instancia nada de outro módulo (princípio XIII).

    `charts_base_url` é o endereço da plataforma que o navegador alcança: sem ele, o `x-axon-charts: embeds` não tem
    de onde carregar o ECharts e os gráficos ficam só na tabela (ADR-052, item 6)."""
    app = FastAPI(title="Axon", version="0.1.0", lifespan=lifespan)
    chart_assets = ChartAssets()
    app.state.chat_service = ChatService(
        engine=engine,
        grants=grants,
        request_ids=request_ids,
        clock=clock,
        conversations=conversations,
        conversation_ids=conversation_ids,
        admission=admission,
        charts=chart_assets.scripts(charts_base_url) if charts_base_url else None,
    )
    app.state.conversation_service = ConversationService(
        store=conversations, clock=clock, retention=conversation_retention
    )
    app.state.authenticator = authenticator
    app.state.directory = directory
    app.state.keys = keys
    app.state.packs = packs
    app.state.admin = admin
    app.state.conversations = conversations
    app.state.health = health
    app.state.conversation_ids = conversation_ids
    app.state.clock = clock
    app.state.mcp = mcp
    app.state.image_limits = image_limits or ImageLimits()
    errors.install(app)
    for surface, prefix in ((PUBLIC_SURFACE, PUBLIC_PREFIX), (PRIVATE_SURFACE, PRIVATE_PREFIX)):
        app.include_router(chat_router(surface=surface), prefix=prefix)
        app.include_router(models_router(surface=surface), prefix=prefix)
        app.include_router(conversations_router(surface=surface), prefix=prefix)
    app.include_router(user_assistants_router(), prefix=PUBLIC_PREFIX)
    if mcp is not None:
        # Sem registry (suítes que não precisam de MCP), as rotas não existem: 404 (research R29).
        app.include_router(user_mcp_router(), prefix=PUBLIC_PREFIX)
        app.include_router(global_mcp_router(), prefix=PRIVATE_PREFIX)
    app.include_router(private_router(), prefix=PRIVATE_PREFIX)
    app.include_router(static_router(chart_assets))
    if admin_seams is not None:
        # Sem os seams de administração (perfis e suítes antigos), a superfície não existe (R43). A rota final do
        # prefixo vem por último: autentica e responde o 404 de não admin a todo caminho que não é rota (FR-024).
        app.add_middleware(AdminHeaders, request_ids=request_ids)
        app.include_router(admin_router(admin_seams, instance or InstanceBranding()), prefix=ADMIN_PREFIX)
        if mcp is not None:
            app.include_router(global_mcp_router(surface=ADMIN_SURFACE), prefix=ADMIN_PREFIX)
        app.include_router(admin_fallback_router(), prefix=ADMIN_PREFIX)
    return app
