"""O harness: roda um conjunto dourado contra um Assistant e monta o relatório (spec 009 US2; research R14 a R22).

Adapter primário sobre seams: cada item vai pelo Execution Engine (005) com a data dele — o único caminho que fixa a
data de referência (ADR-013) —, sob o grant que a 003 resolve para o `Principal` da rodada; o que o motor fez sai do
trace da requisição (009). Métricas de domínio vêm da 002 (ADR-027) e o juiz, quando há, é offline. Nada de internals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from ai_core.assistants.api import (
    AssistantNotFound,
    AssistantUnavailable,
    GrantResolver,
    Principal,
    RateLimited,
    RequestRejected,
)
from ai_core.eval.api import EvalInputError, EvalReport, GoldenItem, GoldenSet, ItemResult
from ai_core.eval.domain.judging import ROUNDS, combine
from ai_core.eval.domain.metrics import MetricSpec, aggregate, core_specs, item_metrics, shares, unseen_evidence
from ai_core.eval.domain.observation import delivered_texts, observe, operation
from ai_core.eval.ports import Clock, Judge
from ai_core.graph.api import (
    ExecutionEngine,
    ExecutionError,
    ExecutionRequest,
    FinalEvent,
    TokenEvent,
)
from ai_core.observability.api import TraceQuery, TraceQueryUnavailable
from ai_core.packs.api import PackEvalMetric, PackEvalMetrics
from axon_ai_contracts import EvalEvidence, EvalItem, EvalObservation, JSONValue

_RESOLVE_ERRORS: Final = (AssistantNotFound, AssistantUnavailable, RequestRejected, RateLimited)


class EvalService:
    """Implementa `EvalHarness`. Montado pela composition root (011) — ou pelos testes — com os seams da plataforma."""

    def __init__(
        self,
        *,
        engine: ExecutionEngine,
        trace: TraceQuery,
        grants: GrantResolver,
        pack_metrics: PackEvalMetrics,
        clock: Clock,
        core_version: str,
        judge: Judge | None = None,
    ) -> None:
        self._engine = engine
        self._trace = trace
        self._grants = grants
        self._pack_metrics = pack_metrics
        self._clock = clock
        self._core_version = core_version
        self._judge = judge

    async def run(
        self, golden: GoldenSet, *, assistant: str, principal: Principal, annotations: Sequence[str] = ()
    ) -> EvalReport:
        try:
            self._trace.trace("eval-probe")
        except TraceQueryUnavailable as error:
            raise EvalInputError(f"o backend de trace não oferece leitura: {error}") from error
        try:
            grant = await self._grants.resolve(model=assistant, principal=principal)
        except _RESOLVE_ERRORS as error:
            raise EvalInputError(f"Assistant {assistant!r}: {error}") from error
        domain = tuple(self._pack_metrics.eval_metrics(grant.composition))
        started = self._clock.now()
        run_id = started.strftime("%Y%m%dT%H%M%S")

        results: list[ItemResult] = []
        per_item: list[Mapping[str, float | None]] = []
        variances: dict[str, list[float]] = {"faithfulness": [], "coverage": []}
        observed: list[tuple[GoldenItem, EvalObservation]] = []
        for item in golden.items:
            result, values, observation, judged = await self._item(item, golden, assistant, principal, run_id, domain)
            results.append(result)
            per_item.append(values)
            for name, variance in judged.items():
                if variance is not None:
                    variances[name].append(variance)
            if observation is not None:
                observed.append((item, observation))

        warnings = unseen_evidence([item for item, _ in observed], [obs.retrieved for _, obs in observed])
        results = [_with_warnings(result, warnings.get(result.id, ())) for result in results]
        executed = [result for result in results if result.failure is None]
        specs: list[MetricSpec] = [
            *core_specs(golden.k),
            *(
                MetricSpec(
                    name=_domain_name(entry), better=entry.metric.better, deterministic=entry.metric.deterministic
                )
                for entry in domain
            ),
        ]
        metrics = [
            *aggregate(specs, per_item, variances={k: _mean(v) for k, v in variances.items()}),
            *shares("flag_rate", [result.flags for result in executed], len(executed)),
            *shares(
                "gate_route",
                [[result.gate_route] for result in executed if result.gate_route],
                sum(1 for result in executed if result.gate_route),
            ),
        ]
        return EvalReport(
            golden_set=golden.name,
            assistant=assistant,
            judge=self._judge.name if self._judge else None,
            started_at=started,
            core_version=self._core_version,
            k=golden.k,
            metrics=metrics,
            items=results,
            invalid=golden.invalid,
            annotations=annotations,
        )

    async def _item(
        self,
        item: GoldenItem,
        golden: GoldenSet,
        assistant: str,
        principal: Principal,
        run_id: str,
        domain: Sequence[PackEvalMetric],
    ) -> tuple[ItemResult, Mapping[str, float | None], EvalObservation | None, dict[str, float | None]]:
        request_id = f"eval-{run_id}-{item.id}"
        failed = {"error_rate": 1.0}
        try:
            grant = await self._grants.resolve(model=assistant, principal=principal)
            events = self._engine.run(
                grant,
                ExecutionRequest(
                    request_id=request_id,
                    messages=[{"role": "user", "content": item.question}],
                    stream=True,
                    reference_time=item.reference_time,
                ),
            )
        except (*_RESOLVE_ERRORS, ExecutionError) as error:
            return ItemResult(id=item.id, failure=f"{type(error).__name__}: {error}"), failed, None, {}

        start = self._clock.monotonic()
        first_token: float | None = None
        final: FinalEvent | None = None
        async for event in events:
            if isinstance(event, TokenEvent) and first_token is None and event.text:
                first_token = self._clock.monotonic()
            elif isinstance(event, FinalEvent):
                final = event
        end = self._clock.monotonic()
        if final is None:
            return ItemResult(id=item.id, failure="a execução terminou sem evento final"), failed, None, {}

        records = self._trace.trace(request_id).records
        observation = observe(final, records)
        cost = operation(
            final,
            records,
            latency_ms=(end - start) * 1000,
            ttft_ms=None if first_token is None else (first_token - start) * 1000,
        )
        metrics: dict[str, Any] = item_metrics(item, observation, cost, golden.k)
        warnings: list[str] = []
        contract_item = _eval_item(item)
        for entry in domain:
            name = _domain_name(entry)
            try:
                value = entry.metric.measure(contract_item, observation)
                metrics[name] = None if value is None else float(value)
            except Exception as error:  # métrica de pack: ausente no item, registrada, nunca derruba a rodada (R18)
                metrics[name] = None
                warnings.append(f"métrica {name} levantou {type(error).__name__}: {error}")
        judged: dict[str, float | None] = {}
        if self._judge is not None:
            passages = delivered_texts(records)
            judgements = [
                await self._judge.judge(
                    question=item.question,
                    answer=final.answer,
                    passages=passages,
                    reference=item.reference_answer,
                    request_id=f"{request_id}:judge:{round_}",
                )
                for round_ in range(1, ROUNDS + 1)
            ]
            combined = combine(judgements)
            metrics["faithfulness"] = combined.faithfulness
            metrics["coverage"] = combined.coverage if item.reference_answer else None
            judged = {
                "faithfulness": combined.faithfulness_variance,
                "coverage": combined.coverage_variance if item.reference_answer else None,
            }
        result = ItemResult(
            id=item.id,
            metrics=metrics,
            citations=[cast("dict[str, JSONValue]", dict(citation)) for citation in final.citations],
            flags=sorted(final.flags),
            issue_kinds=[issue.kind for issue in final.errors],
            gate_route=cost.gate_route,
            warnings=warnings,
        )
        return result, metrics, observation, judged


def _domain_name(entry: PackEvalMetric) -> str:
    return f"{entry.pack}:{entry.metric.name}"


def _eval_item(item: GoldenItem) -> EvalItem:
    def evidences(values: Sequence[Any]) -> tuple[EvalEvidence, ...]:
        return tuple(EvalEvidence(document=e.document, section=e.section, chunk_id=e.chunk_id) for e in values)

    return EvalItem(
        id=item.id,
        question=item.question,
        reference_time=item.reference_time,
        expected_documents=evidences(item.expected_documents),
        reference_answer=item.reference_answer,
        expected_citations=evidences(item.expected_citations),
        extra=item.extra,
    )


def _with_warnings(result: ItemResult, extra: Sequence[str]) -> ItemResult:
    if not extra:
        return result
    return ItemResult(
        id=result.id,
        metrics=result.metrics,
        citations=result.citations,
        flags=result.flags,
        issue_kinds=result.issue_kinds,
        gate_route=result.gate_route,
        failure=result.failure,
        warnings=[*result.warnings, *extra],
    )


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None
