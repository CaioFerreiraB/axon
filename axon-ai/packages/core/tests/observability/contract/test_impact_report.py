"""T091 — conformidade do impacto no `UsageStore` (memória e Postgres) e o `ImpactService` (009 US9; R48 a R51).

As duas versões do armazenamento devem dar o mesmo relatório que a agregação de referência do domínio monta das mesmas
linhas (SC-010): baldes no dia local do fuso, chaves, cobertura, respostas estimadas e o modelo mais recente por chave.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta

import pytest
from conftest import Stores

from axon_ai.observability.adapters.memory import FixedClock, FixedImpactEstimator
from axon_ai.observability.api import ImpactGrain, ImpactQuery, ImpactReport, InvalidQuery
from axon_ai.observability.domain.impact import aggregate_impact, build_impact_report, window
from axon_ai.observability.domain.usage_records import IMPACT_COLUMNS, ImpactEstimate, ModelCallRow
from axon_ai.observability.service import ImpactService

pytestmark = pytest.mark.us9

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def _estimate(scale: float, *, match: str = "exact", model: str = "openai/gpt-4.1-mini") -> ImpactEstimate:
    values = {
        column: scale * (index + 1) * (1.0 if column.endswith("_min") else 2.0)
        for index, column in enumerate(IMPACT_COLUMNS)
    }
    return ImpactEstimate(model=model, match=match, zone="USA", version="0.11.3", values=values)  # type: ignore[arg-type]


def _call(at: datetime, rid: str, **changes: object) -> ModelCallRow:
    fields: dict[str, object] = {
        "request_id": rid,
        "at": at,
        "origin": "production",
        "assistant": "geral",
        "provider": "openrouter",
        "model": "openai/gpt-4.1-mini",
        "role": "generation",
        "input_tokens": 100,
        "output_tokens": 40,
        "duration_ms": 2500.0,
        "impact": _estimate(0.001),
        "impact_tried": True,
    }
    fields.update(changes)
    return ModelCallRow(**fields)  # type: ignore[arg-type]


CALLS = [
    _call(datetime(2026, 9, 30, 2, 30, tzinfo=UTC), "r1"),  # dia 29/09 em São Paulo: 3º trimestre
    _call(datetime(2026, 9, 30, 2, 31, tzinfo=UTC), "r1", role="controller", impact=_estimate(0.002)),
    _call(
        datetime(2026, 10, 5, 15, tzinfo=UTC),
        "r2",
        model="z-ai/glm-5.3-flash",
        impact=_estimate(0.003, match="approximate", model="mistralai/zai-glm-5-3"),
    ),
    _call(
        datetime(2026, 10, 6, 15, tzinfo=UTC), "r3", assistant=None, provider="ollama", model="qwen3:1.7b", impact=None
    ),
    _call(datetime(2026, 10, 7, 15, tzinfo=UTC), "r4", failed=True, output_tokens=0, impact=None, impact_tried=False),
    _call(datetime(2026, 10, 8, 15, tzinfo=UTC), "r5", origin="evaluation", impact=_estimate(0.5)),
    _call(datetime(2026, 10, 20, 15, tzinfo=UTC), "r6", assistant="interno", impact=_estimate(0.004)),
]


def _service(stores: Stores, **changes: object) -> ImpactService:
    options: dict[str, object] = {
        "store": stores.usage,
        "clock": FixedClock(NOW),
        "estimator": FixedImpactEstimator(version="0.11.3"),
        "tree_kg_co2e": 140.0,
        "retention_days": 400,
    }
    options.update(changes)
    return ImpactService(**options)  # type: ignore[arg-type]


def _reference(query: ImpactQuery) -> ImpactReport:
    start, end = window(query)
    agg = aggregate_impact(
        CALLS, start=start, end=end, tz=query.tz, grain=query.grain, by=query.by, origin=query.origin
    )
    return build_impact_report(query, agg, None, version="0.11.3", tree_kg_co2e=140.0)


def _numbers(metrics: object) -> list[float]:
    return [value for pair in dataclasses.astuple(metrics) for value in pair]  # type: ignore[call-overload]


def _same(left: ImpactReport, right: ImpactReport) -> None:
    """Iguais, com os floats do banco dentro do erro de soma."""

    def flat(report: ImpactReport) -> list[object]:
        out: list[object] = []
        for bucket in report.buckets:
            out += [bucket.start, bucket.end, bucket.calls, bucket.responses, bucket.estimated_responses]
            out += [_numbers(bucket.metrics)]
            out += [(r.key, r.calls, r.coverage, r.metrics.gwp_kgco2eq.mean) for r in bucket.rows]
        for row in report.rows:
            out += [
                row.key,
                row.impact_model,
                row.match,
                row.calls,
                row.responses,
                row.estimated_responses,
                row.estimated_output_tokens,
                row.coverage,
                _numbers(row.metrics),
            ]
        assert report.totals is not None
        out += [
            report.totals.coverage,
            report.totals.responses,
            report.totals.estimated_responses,
            report.totals.estimated_output_tokens,
            report.totals.trees,
        ]
        return out

    def close(a: object, b: object) -> bool:
        if isinstance(a, float) and isinstance(b, float):
            return a == pytest.approx(b, rel=1e-9, abs=1e-15)
        if isinstance(a, list | tuple) and isinstance(b, list | tuple):
            return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b, strict=True))
        return a == b

    got, expected = flat(right), flat(left)
    assert close(got, expected), (got, expected)


@pytest.mark.parametrize("grain", ["day", "week", "month", "quarter", "semester"])
@pytest.mark.parametrize("by", ["model", "assistant"])
async def test_armazenamento_igual_a_referencia(stores: Stores, grain: ImpactGrain, by: str) -> None:
    await stores.usage.append(CALLS, [])
    query = ImpactQuery(start=date(2026, 9, 1), end=date(2026, 10, 31), tz="America/Sao_Paulo", grain=grain, by=by)  # type: ignore[arg-type]
    report = await _service(stores).report(query)
    _same(_reference(query), report)


async def test_numeros_do_trimestre(stores: Stores) -> None:
    await stores.usage.append(CALLS, [])
    report = await _service(stores).report(
        ImpactQuery(start=date(2026, 9, 1), end=date(2026, 10, 31), tz="America/Sao_Paulo", grain="quarter")
    )
    assert [(b.start, b.end, b.calls) for b in report.buckets] == [
        (date(2026, 9, 1), date(2026, 9, 30), 2),
        (date(2026, 10, 1), date(2026, 10, 31), 4),
    ]
    totals = report.totals
    assert totals is not None
    assert (totals.coverage.calls, totals.coverage.eligible, totals.coverage.estimated) == (6, 5, 4)
    assert totals.coverage.approximate == 1
    assert (totals.responses, totals.estimated_responses) == (5, 3)
    # SC-010: o total é a soma do que foi gravado (produção, elegível, estimado).
    gwp_min = sum(c.impact.values["gwp_kgco2eq_min"] for c in CALLS if c.impact and c.origin == "production")
    assert totals.metrics.gwp_kgco2eq.min == pytest.approx(gwp_min)
    assert totals.trees == pytest.approx(totals.metrics.gwp_kgco2eq.mean / 140.0)
    glm = next(row for row in report.rows if row.key == "openrouter/z-ai/glm-5.3-flash")
    assert (glm.impact_model, glm.match) == ("mistralai/zai-glm-5-3", "approximate")


async def test_periodo_anterior_e_origem(stores: Stores) -> None:
    await stores.usage.append(CALLS, [])
    service = _service(stores)
    october = ImpactQuery(start=date(2026, 10, 1), end=date(2026, 10, 31), tz="UTC", grain="week")
    report = await service.report(october)
    assert report.previous is not None and report.previous.coverage.calls == 2  # de 01 a 30/09 em UTC
    evaluation = await service.report(dataclasses.replace(october, origin="evaluation"))
    assert evaluation.totals is not None and evaluation.totals.coverage.calls == 1


async def test_recorte_pela_retencao_e_desligado(stores: Stores) -> None:
    await stores.usage.append(CALLS, [])
    clipped = await _service(stores, retention_days=40).report(
        ImpactQuery(start=date(2026, 9, 1), end=date(2026, 10, 31), tz="UTC", grain="month")
    )
    assert clipped.clipped_start == (NOW - timedelta(days=40)).date()
    assert clipped.buckets[0].start == clipped.clipped_start
    off = await _service(stores, estimator=None).report(ImpactQuery(start=date(2026, 9, 1), end=date(2026, 10, 31)))
    assert (off.enabled, off.buckets, off.totals) == (False, (), None)


def test_dia_acima_de_366_e_recusado() -> None:
    with pytest.raises(InvalidQuery) as error:
        ImpactQuery(start=date(2025, 1, 1), end=date(2026, 3, 1), grain="day")
    assert error.value.field == "grain"


async def test_nao_estimadas_e_gravacao_so_onde_nulo(stores: Stores) -> None:
    pending = _call(datetime(2026, 10, 9, tzinfo=UTC), "r7", impact=None, impact_tried=False)
    await stores.usage.append([*CALLS, pending], [])
    found = await stores.usage.unestimated(10)
    assert [(c.provider, c.model, c.output_tokens) for c in found] == [("openrouter", "openai/gpt-4.1-mini", 40)]
    await stores.usage.set_impacts([(found[0].id, _estimate(0.01))])
    assert await stores.usage.unestimated(10) == ()
    await stores.usage.set_impacts([(found[0].id, None)])  # já estimada: não muda
    report = await _service(stores).report(ImpactQuery(start=date(2026, 10, 9), end=date(2026, 10, 9), tz="UTC"))
    assert report.totals is not None and report.totals.coverage.estimated == 1
