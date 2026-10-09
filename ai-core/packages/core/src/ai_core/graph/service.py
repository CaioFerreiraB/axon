"""Serviço do motor: implementa o seam Execution Engine (contracts/execution-engine.md).

Valida a requisição, fixa a data de referência, monta o plano da execução a partir do grant e delega ao adapter de
fluxo. Não conhece estado, nós nem framework: fala com o grafo pela porta `FlowRuntime`, e é isso que torna a
reescrita do grafo uma troca de objeto injetado (ADR-011, SC-001). Não importa `adapters/`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from ai_core.capabilities.api import Capabilities
from ai_core.graph.api import (
    FLOW_RAG_FIRST,
    ExecutionEvent,
    ExecutionGrant,
    ExecutionRequest,
    ExecutionRequestInvalid,
    FinalEvent,
    RagSettings,
)
from ai_core.graph.domain.limits import effective_limit
from ai_core.graph.domain.outcome import succeeded
from ai_core.graph.domain.request import TOOL_FLOWS, offered, optional_roles, required_roles, validate
from ai_core.graph.ports import Clock, ExecutionPlan, FlowRuntime
from ai_core.llm.api import ModelRole, ModelRouter, ModelRouting, ModelRoutingError
from ai_core.observability.api import ExecutionFinished, ExecutionStarted, TraceSink
from ai_core.packs.api import PackHooks

CANCELLED = "cancelled"


class ExecutionService:
    """Um serviço por processo, montado pela composition root (spec 011) com os seams e adapters do perfil."""

    def __init__(
        self,
        *,
        flows: FlowRuntime,
        hooks: PackHooks,
        routing: ModelRouting,
        trace: TraceSink,
        clock: Clock,
        capabilities: Capabilities | None = None,
        rag: RagSettings | None = None,
    ) -> None:
        self._flows = flows
        self._hooks = hooks
        self._routing = routing
        self._trace = trace
        self._clock = clock
        self._capabilities = capabilities
        self._rag = rag or RagSettings()

    def flows(self) -> frozenset[str]:
        """Nomes de flow disponíveis; `assistants validate` (003) os usa como dado. Sem o gateway de tools da 004, os
        flows que dependem dele não são oferecidos (research R16)."""
        return offered(self._flows.names(), tools=self._capabilities is not None)

    def flow_roles(self) -> Mapping[str, tuple[ModelRole, ...]]:
        """Os papéis por flow oferecido, da mesma regra que `run` aplica (`domain/request.py`, ADR-019)."""
        return {name: required_roles(name) for name in sorted(self.flows())}

    def run(self, grant: ExecutionGrant, request: ExecutionRequest) -> AsyncIterator[ExecutionEvent]:
        """Valida e devolve o fluxo de eventos.

        Não é gerador de propósito: a validação precisa levantar **nesta chamada**, para que a 008 responda 4xx sem
        abrir o stream e sem custo (research R5).
        """
        question = validate(request, grant, self.flows())
        router = self._routing.for_execution(policy=grant.models, request_id=request.request_id)
        declared = set(grant.models.configured_roles())
        _resolve_roles(router, (*required_roles(grant.flow), *(r for r in optional_roles(grant.flow) if r in declared)))
        reference_time = request.reference_time or self._clock.now()
        tools = grant.flow in TOOL_FLOWS
        rag_first = grant.flow == FLOW_RAG_FIRST
        plan = ExecutionPlan(
            flow=grant.flow,
            request_id=request.request_id,
            assistant=grant.assistant,
            reference_time=reference_time,
            question=question,
            messages=request.messages,
            composition=grant.composition,
            hooks=self._hooks,
            router=router,
            trace=self._trace,
            grant=grant,
            capabilities=self._capabilities if tools else None,
            max_iterations=effective_limit(grant.limits.max_iterations) if tools else None,
            max_context_tokens=grant.limits.max_context_tokens if tools else None,
            rag=self._rag if rag_first else None,
            escalate=rag_first and "controller" in declared,
        )
        return self._events(plan, stream=request.stream)

    async def _events(self, plan: ExecutionPlan, *, stream: bool) -> AsyncIterator[ExecutionEvent]:
        self._trace.emit(
            ExecutionStarted(
                request_id=plan.request_id,
                assistant=plan.assistant,
                flow=plan.flow,
                packs=plan.composition.packs,
                reference_time=plan.reference_time,
            )
        )
        started = self._clock.monotonic()
        final: FinalEvent | None = None
        try:
            async for event in self._flows.events(plan):
                if isinstance(event, FinalEvent):
                    final = event
                elif not stream:
                    continue  # sem streaming, o consumidor recebe só o evento final
                yield event
        finally:
            self._trace.emit(
                ExecutionFinished(
                    request_id=plan.request_id,
                    ok=final is not None and succeeded(final),
                    duration_ms=max(0.0, (self._clock.monotonic() - started) * 1000),
                    reason=None if final is not None else CANCELLED,
                )
            )


def _resolve_roles(router: ModelRouter, roles: tuple[ModelRole, ...]) -> None:
    """Papéis do flow resolvidos antes do primeiro evento (FR-013, research R25) — os exigidos e os opcionais que o
    grant declara (R40). Resolver não faz I/O (006)."""
    for role in roles:
        try:
            router.for_role(role)
        except ModelRoutingError as error:
            raise ExecutionRequestInvalid(f"papel '{role}': {error}") from error
