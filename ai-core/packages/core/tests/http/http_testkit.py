"""Fábricas dos testes da 008: a app montada em processo, com o motor real e o provider simulado.

Só o modelo é simulado — API, motor, hooks de pack e roteador de modelos são os de verdade (research R10).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Final

from fastapi import FastAPI
from graph_testkit import ASSISTANT, MODEL, Grant, RecordingTraceSink, ScriptedHooks, provider

from ai_core.assistants.api import SCHEME_OF_SURFACE, AssistantNotFound, Principal
from ai_core.graph.adapters.clock import FixedClock as GraphFixedClock
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.api import ExecutionEvent, FinalEvent, ProgressEvent, TokenEvent
from ai_core.graph.service import ExecutionService
from ai_core.http.adapters.app import create_app
from ai_core.http.adapters.conversations_memory import InMemoryConversationStore
from ai_core.http.adapters.development import FixedClock, SequentialRequestIds, StaticHealthProvider
from ai_core.llm.service import ModelRoutingService

CREATED: Final = datetime(2026, 9, 21, 12, tzinfo=UTC)
MODEL_ID: Final = f"{ASSISTANT}/{MODEL}"
ANONYMOUS: Final = "user:anonymous"


class StaticGrants:
    """Resolvedor de grant da Fase 1: o que a 011 monta da configuração, e a 003 substitui na Fase 2."""

    def __init__(self, *, known: Sequence[str] = (ASSISTANT,)) -> None:
        self._known = tuple(known)
        self.calls: list[tuple[str, str]] = []

    async def resolve(self, *, model: str, principal: Principal) -> Grant:
        self.calls.append((model, principal.subject))
        assistant = model.split("/", 1)[0]
        if assistant not in self._known:
            raise AssistantNotFound(f"assistant '{assistant}' não existe ou não é visível")
        return Grant(assistant=assistant)


class RejectingAuthenticator:
    """Autenticador que recusa qualquer credencial — prova o 401."""

    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None:
        return None


class SurfaceRecordingAuthenticator:
    """Aceita tudo e guarda em qual superfície foi chamado."""

    def __init__(self) -> None:
        self.surfaces: list[str] = []

    async def authenticate(self, *, surface: str, credential: str | None) -> Principal:
        self.surfaces.append(surface)
        return Principal(subject=ANONYMOUS, scheme=SCHEME_OF_SURFACE[surface])


class HoldingEngine:
    """Motor programado da fila (Fase 7, T064): cada execução emite o progresso de `generate` e só emite o token e o
    evento final depois de `gate` ser liberado; conta as execuções simultâneas (`running`, `peak`) e as chamadas."""

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.running = 0
        self.peak = 0
        self.calls = 0

    def flows(self) -> tuple[str, ...]:
        return ("chat",)

    def flow_roles(self) -> Mapping[str, tuple[str, ...]]:
        return {"chat": ("generation",)}

    def run(self, grant: Any, request: Any) -> AsyncIterator[ExecutionEvent]:
        return self._run()

    async def _run(self) -> AsyncIterator[ExecutionEvent]:
        self.calls += 1
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            yield ProgressEvent(stage="generate")
            await self.gate.wait()
            yield TokenEvent(text="ok")
            yield FinalEvent(answer="ok")
        finally:
            self.running -= 1


def engine(
    *,
    hooks: Any = None,
    llm: Any = None,
    trace: RecordingTraceSink | None = None,
) -> ExecutionService:
    """Motor real, com o adapter de fluxo real e o provider simulado da 006."""
    sink = trace or RecordingTraceSink()
    clock = GraphFixedClock(CREATED, readings=[1.0, 1.25])
    return ExecutionService(
        flows=langgraph_runtime(),
        hooks=hooks or ScriptedHooks(),
        routing=ModelRoutingService(providers={"ollama": llm or provider()}, trace=sink, clock=clock),
        trace=sink,
        clock=clock,
    )


def app(
    *,
    hooks: Any = None,
    llm: Any = None,
    trace: RecordingTraceSink | None = None,
    authenticator: Any = None,
    grants: Any = None,
    **overrides: Any,
) -> FastAPI:
    """A app como a 011 a montará, com os adapters de desenvolvimento."""
    return app_with(
        engine(hooks=hooks, llm=llm, trace=trace),
        authenticator=authenticator or SurfaceRecordingAuthenticator(),
        grants=grants or StaticGrants(),
        **overrides,
    )


def app_with(engine_: Any, *, authenticator: Any, grants: Any, **overrides: Any) -> FastAPI:
    """`create_app` com defaults para tudo o que o teste não declara: serviços reais da 003 em memória, Pack Registry
    falso, conversas em memória, saúde ok, identificadores sequenciais e relógio fixo."""
    from assistants_testkit import access_service, assistants_service, config, default_registry

    access = overrides.pop("access", None) or access_service()
    parts: dict[str, Any] = {
        "directory": assistants_service(config()),
        "keys": access,
        "packs": default_registry(),
        "admin": access,
        "conversations": InMemoryConversationStore(),
        "health": StaticHealthProvider(),
        "request_ids": SequentialRequestIds(),
        "conversation_ids": SequentialRequestIds(prefix="conv"),
        "clock": FixedClock(CREATED),
    }
    parts.update(overrides)
    return create_app(engine=engine_, authenticator=authenticator, grants=grants, **parts)


def body(**overrides: Any) -> dict[str, Any]:
    """Corpo mínimo no formato OpenAI."""
    base: dict[str, Any] = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "qual é a capital?"}],
    }
    return base | overrides


def chunks_of(text: str) -> list[dict[str, Any]]:
    """Lê um corpo SSE e devolve os chunks, sem o marcador de fim."""
    out: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        line = block.strip()
        if not line.startswith("data: "):
            continue
        payload = line.removeprefix("data: ")
        if payload == "[DONE]":
            continue
        out.append(json.loads(payload))
    return out


def has_done(text: str) -> bool:
    return text.rstrip().endswith("data: [DONE]")


def answer_of(chunks: Sequence[dict[str, Any]]) -> str:
    return "".join(chunk["choices"][0]["delta"].get("content", "") for chunk in chunks)


# ---------------------------------------------------------------------------------------------------------------------
# Fase 2: a app com os serviços reais da 003 (research R24)
# ---------------------------------------------------------------------------------------------------------------------

ANA_TOKEN: Final = "tok-ana"
BIA_TOKEN: Final = "tok-bia"
CAIO_TOKEN: Final = "tok-caio"
"""Tokens OIDC do verificador estático: `user:ana` sem grupos; `user:bia` do grupo `chefia`; `user:caio` — o mesmo
subject da `ADMIN_KEY`, pela superfície pública."""

ADMIN_KEY: Final = "aic_00000000000000a1_admin"
"""Chave de `user:caio`, do grupo de administração `operadores`."""

SVC_KEY: Final = "aic_00000000000000b2_servico"
"""Chave de `svc:ingestor`, sem grupos."""


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class Platform:
    """A app montada com os serviços reais da 003 e os adapters em memória, mais os objetos para inspeção."""

    def __init__(self, data: Any = None, *, llm: Any = None, trace: Any = None, **overrides: Any) -> None:
        from assistants_testkit import (
            POLICIES,
            T0,
            MutableClock,
            access_service,
            assistant,
            assistants_service,
            claims,
            config,
            private,
        )

        from ai_core.assistants.adapters.memory import (
            InMemoryApiKeyStore,
            InMemoryUserAssistantStore,
            StaticOidcVerifier,
        )
        from ai_core.assistants.api import ApiKeyInfo
        from ai_core.assistants.domain.keys import ApiKeyRecord, hash_key

        self.clock = overrides.pop("assistants_clock", None) or MutableClock()
        keys = InMemoryApiKeyStore()
        for plaintext, key_id, subject, groups in (
            (ADMIN_KEY, "00000000000000a1", "user:caio", frozenset({"operadores"})),
            (SVC_KEY, "00000000000000b2", "svc:ingestor", frozenset()),
        ):
            info = ApiKeyInfo(key_id=key_id, subject=subject, groups=groups, created_at=T0)
            keys.seed(ApiKeyRecord(info=info, key_hash=hash_key(plaintext)))
        oidc = StaticOidcVerifier(
            {
                ANA_TOKEN: claims("ana", ttl=3600),
                BIA_TOKEN: claims("bia", groups=["chefia"], ttl=3600),
                CAIO_TOKEN: claims("caio", ttl=3600),
            }
        )
        self.access = access_service(keys=keys, oidc=oidc, clock=self.clock)
        self.users = overrides.pop("users", None) or InMemoryUserAssistantStore()
        self.mcp = overrides.pop("mcp", None)
        """O registry da 007 (Fase 3): diretório de MCP da 003 e rotas de MCP da API, quando dado."""
        self.assistants = assistants_service(
            data
            if data is not None
            else config(
                {
                    "geral": assistant(description="uso geral"),
                    "privado": private(allow=["user:caio"], schemes=["api_key"]),
                    "chefia": private(allow=["group:chefia"], schemes=["oidc"]),
                },
                policies=POLICIES,
            ),
            users=self.users,
            clock=self.clock,
            mcp=self.mcp,
        )
        if self.mcp is not None:
            overrides["mcp"] = self.mcp
        self.conversations = overrides.pop("conversations", None) or InMemoryConversationStore()
        self.app = app_with(
            engine(llm=llm, trace=trace),
            authenticator=self.access,
            grants=self.assistants,
            directory=self.assistants,
            keys=self.access,
            admin=self.access,
            conversations=self.conversations,
            **overrides,
        )
