"""Serviço do motor: implementa o seam Execution Engine (contracts/execution-engine.md).

Valida a requisição, fixa a data de referência, monta o plano da execução a partir do grant e delega ao adapter de
fluxo. Não conhece estado, nós nem framework: fala com o grafo pela porta `FlowRuntime`, e é isso que torna a
reescrita do grafo uma troca de objeto injetado (ADR-011, SC-001). Não importa `adapters/`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ai_core.graph.api import (
    ExecutionEvent,
    ExecutionGrant,
    ExecutionRequest,
    FinalEvent,
)
from ai_core.graph.domain.outcome import succeeded
from ai_core.graph.domain.request import validate
from ai_core.graph.ports import Clock, ExecutionPlan, FlowRuntime
from ai_core.llm.api import ModelRouting
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
    ) -> None:
        self._flows = flows
        self._hooks = hooks
        self._routing = routing
        self._trace = trace
        self._clock = clock

    def flows(self) -> frozenset[str]:
        """Nomes de flow disponíveis; `assistants validate` (003) os usa como dado."""
        return self._flows.names()

    def run(self, grant: ExecutionGrant, request: ExecutionRequest) -> AsyncIterator[ExecutionEvent]:
        """Valida e devolve o fluxo de eventos.

        Não é gerador de propósito: a validação precisa levantar **nesta chamada**, para que a 008 responda 4xx sem
        abrir o stream e sem custo (research R5).
        """
        question = validate(request, grant, self._flows.names())
        reference_time = request.reference_time or self._clock.now()
        plan = ExecutionPlan(
            flow=grant.flow,
            request_id=request.request_id,
            assistant=grant.assistant,
            reference_time=reference_time,
            question=question,
            messages=request.messages,
            composition=grant.composition,
            hooks=self._hooks,
            router=self._routing.for_execution(policy=grant.models, request_id=request.request_id),
            trace=self._trace,
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
