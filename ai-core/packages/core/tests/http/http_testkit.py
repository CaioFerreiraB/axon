"""Fábricas dos testes da 008: a app montada em processo, com o motor real e o provider simulado.

Só o modelo é simulado — API, motor, hooks de pack e roteador de modelos são os de verdade (research R10).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

from fastapi import FastAPI
from graph_testkit import ASSISTANT, MODEL, Grant, RecordingTraceSink, ScriptedHooks, provider

from ai_core.graph.adapters.clock import FixedClock as GraphFixedClock
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.service import ExecutionService
from ai_core.http.adapters.app import create_app
from ai_core.http.adapters.development import DevelopmentPrincipal, FixedClock, SequentialRequestIds
from ai_core.http.ports import AssistantNotFound, Principal
from ai_core.llm.service import ModelRoutingService

CREATED: Final = datetime(2026, 9, 21, 12, tzinfo=UTC)
MODEL_ID: Final = f"{ASSISTANT}/{MODEL}"


class StaticGrants:
    """Resolvedor de grant da Fase 1: o que a 011 monta da configuração, e a 003 substitui na Fase 2."""

    def __init__(self, *, known: Sequence[str] = (ASSISTANT,)) -> None:
        self._known = tuple(known)
        self.calls: list[tuple[str, str]] = []

    async def resolve(self, *, model: str, principal: Principal) -> Grant:
        self.calls.append((model, principal.id))
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
        return DevelopmentPrincipal()


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
) -> FastAPI:
    """A app como a 011 a montará, com os adapters de desenvolvimento."""
    return create_app(
        engine=engine(hooks=hooks, llm=llm, trace=trace),
        authenticator=authenticator or SurfaceRecordingAuthenticator(),
        grants=grants or StaticGrants(),
        request_ids=SequentialRequestIds(),
        clock=FixedClock(CREATED),
    )


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
