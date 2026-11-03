"""T089 — domínio do impacto ambiental (009 US9; ADR-056; research R45, R48, R49): nomes, grãos e o relatório."""

from __future__ import annotations

import difflib
from datetime import UTC, date, datetime, timedelta

import pytest

from axon_ai.observability.api import ImpactQuery, InvalidQuery
from axon_ai.observability.domain.impact import (
    aggregate_impact,
    bucket_start,
    buckets,
    build_impact_report,
    build_index,
    family,
    normalize,
    resolve,
    window,
)
from axon_ai.observability.domain.usage_records import IMPACT_COLUMNS, ImpactEstimate, ModelCallRow

pytestmark = pytest.mark.us9

BASE = (
    ("openai", "gpt-4.1-mini"),
    ("openai", "gpt-4.1-nano"),
    ("mistralai", "zai-glm-5-3"),
    ("google_genai", "gemini-2.5-flash"),
    ("huggingface_hub", "meta-llama/Meta-Llama-3.1-70B-Instruct"),
    ("huggingface_hub", "mistralai/Mistral-7B-Instruct-v0.3"),
    ("mistralai", "mistral-7b-instruct-v0.3"),
)
INDEX = build_index(BASE)


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio() * 100


def test_normalizacao_e_familia() -> None:
    assert normalize("Qwen3:1.7B") == "qwen3"
    assert normalize("gpt-4.1_mini") == "gpt-4-1-mini"
    assert normalize("Claude Sonnet  4.5") == "claude-sonnet-4-5"
    assert family("glm-5.3-flash") == "glm"
    assert family("qwen3:1.7b") == "qwen"
    assert family("llama-3.3-70b-instruct") == "llama"


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        ("openrouter", "openai/gpt-4.1-mini", ("openai", "gpt-4.1-mini", "exact")),
        ("openai", "gpt-4.1-nano", ("openai", "gpt-4.1-nano", "exact")),
        ("openrouter", "z-ai/glm-5.3-flash", ("mistralai", "zai-glm-5-3", "approximate")),
        (
            "openrouter",
            "meta-llama/llama-3.3-70b-instruct",
            ("huggingface_hub", "meta-llama/Meta-Llama-3.1-70B-Instruct", "approximate"),
        ),
        ("ollama", "qwen3:1.7b", None),
        ("openrouter", "deepseek/deepseek-chat", None),
    ],
)
def test_resolucao_exata_aproximada_e_sem_par(provider: str, model: str, expected: tuple[str, str, str] | None) -> None:
    found = resolve(provider, model, INDEX, similarity)
    assert (None if found is None else (found.provider, found.name, found.match)) == expected


def test_glm_nunca_cai_no_gemini() -> None:
    found = resolve("openrouter", "z-ai/glm-5.3-flash", INDEX, similarity)
    assert found is not None and "gemini" not in found.name


def test_empate_entre_provedores_pelo_fornecedor_e_pela_ordem() -> None:
    by_vendor = resolve("openrouter", "mistralai/mistral-7b-instruct-v0.3", INDEX, similarity)
    assert by_vendor is not None and (by_vendor.provider, by_vendor.match) == ("mistralai", "exact")
    no_vendor = resolve("ollama", "mistral-7b-instruct-v0.3", INDEX, similarity)
    assert no_vendor is not None and no_vendor.provider == "mistralai"  # vem antes de huggingface_hub na ordem fixa


@pytest.mark.parametrize(
    ("day", "grain", "start"),
    [
        (date(2026, 11, 5), "day", date(2026, 11, 5)),
        (date(2026, 11, 5), "week", date(2026, 11, 2)),
        (date(2026, 11, 2), "week", date(2026, 11, 2)),
        (date(2026, 11, 5), "month", date(2026, 11, 1)),
        (date(2026, 11, 5), "quarter", date(2026, 10, 1)),
        (date(2026, 11, 5), "semester", date(2026, 7, 1)),
        (date(2026, 3, 15), "semester", date(2026, 1, 1)),
        (date(2027, 1, 1), "week", date(2026, 12, 28)),
    ],
)
def test_inicio_do_balde(day: date, grain: str, start: date) -> None:
    assert bucket_start(day, grain) == start  # type: ignore[arg-type]


def test_baldes_recortados_ao_periodo() -> None:
    assert buckets(date(2026, 7, 16), date(2026, 8, 5), "month") == (
        (date(2026, 7, 16), date(2026, 7, 31)),
        (date(2026, 8, 1), date(2026, 8, 5)),
    )
    weeks = buckets(date(2026, 7, 16), date(2026, 10, 13), "week")
    assert weeks[0] == (date(2026, 7, 16), date(2026, 7, 19))
    assert weeks[-1] == (date(2026, 10, 12), date(2026, 10, 13))
    assert len(weeks) == 14
    assert buckets(date(2026, 1, 1), date(2026, 12, 31), "semester") == (
        (date(2026, 1, 1), date(2026, 6, 30)),
        (date(2026, 7, 1), date(2026, 12, 31)),
    )


def test_consulta_recusa_dia_longo_e_grao_desconhecido() -> None:
    with pytest.raises(InvalidQuery) as error:
        ImpactQuery(start=date(2025, 1, 1), end=date(2026, 2, 1), grain="day")
    assert error.value.field == "grain"
    ImpactQuery(start=date(2025, 1, 1), end=date(2026, 2, 1), grain="month")
    with pytest.raises(InvalidQuery) as error:
        ImpactQuery(start=date(2026, 1, 1), end=date(2026, 2, 1), grain="year")  # type: ignore[arg-type]
    assert error.value.field == "grain"


def _estimate(gwp: float, *, match: str = "exact", model: str = "openai/gpt-4.1-mini") -> ImpactEstimate:
    values = {column: 0.0 for column in IMPACT_COLUMNS}
    values.update(gwp_kgco2eq_min=gwp * 0.5, gwp_kgco2eq_max=gwp * 1.5, energy_kwh_min=gwp, energy_kwh_max=gwp * 3)
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
        "output_tokens": 50,
        "duration_ms": 3000.0,
        "impact": _estimate(140.0),
        "impact_tried": True,
    }
    fields.update(changes)
    return ModelCallRow(**fields)  # type: ignore[arg-type]


def test_relatorio_media_cobertura_respostas_e_arvores() -> None:
    july = datetime(2026, 7, 20, 12, tzinfo=UTC)
    august = datetime(2026, 8, 3, 12, tzinfo=UTC)
    calls = [
        _call(july, "r1"),
        _call(july + timedelta(minutes=1), "r1", role="controller"),  # mesma resposta
        _call(august, "r2", model="z-ai/glm-5.3-flash", impact=_estimate(140.0, match="approximate")),
        _call(august, "r3", model="qwen3:1.7b", provider="ollama", impact=None),  # sem par
        _call(august, "r4", failed=True, output_tokens=0, impact=None, impact_tried=False),  # inelegível
        _call(august, "r5", origin="evaluation"),  # outra origem
    ]
    query = ImpactQuery(start=date(2026, 7, 16), end=date(2026, 8, 5), tz="UTC", grain="month")
    start, end = window(query)
    agg = aggregate_impact(calls, start=start, end=end, tz="UTC", grain="month", by="model", origin="production")
    report = build_impact_report(query, agg, None, version="0.11.3", tree_kg_co2e=140.0)

    assert [(b.start, b.end, b.calls, b.responses, b.estimated_responses) for b in report.buckets] == [
        (date(2026, 7, 16), date(2026, 7, 31), 2, 1, 1),
        (date(2026, 8, 1), date(2026, 8, 5), 3, 3, 1),
    ]
    totals = report.totals
    assert totals is not None
    assert (totals.coverage.calls, totals.coverage.eligible, totals.coverage.estimated) == (5, 4, 3)
    assert totals.coverage.approximate == 1
    assert totals.coverage.unestimated == 1
    assert (totals.responses, totals.estimated_responses) == (4, 2)
    assert totals.estimated_output_tokens == 150
    assert totals.metrics.gwp_kgco2eq.min == pytest.approx(210.0)
    assert totals.metrics.gwp_kgco2eq.mean == pytest.approx(420.0)
    assert totals.trees == pytest.approx(3.0)
    glm = next(row for row in report.rows if row.key == "openrouter/z-ai/glm-5.3-flash")
    assert (glm.impact_model, glm.match) == ("openai/gpt-4.1-mini", "approximate")
    assert report.rows[0].metrics.gwp_kgco2eq.mean >= report.rows[-1].metrics.gwp_kgco2eq.mean


def test_relatorio_sem_chamadas_tem_baldes_vazios() -> None:
    query = ImpactQuery(start=date(2026, 7, 1), end=date(2026, 7, 31), tz="UTC", grain="week")
    start, end = window(query)
    agg = aggregate_impact([], start=start, end=end, tz="UTC", grain="week", by="model", origin="production")
    report = build_impact_report(query, agg, None, version="0.11.3", tree_kg_co2e=140.0)
    assert len(report.buckets) == 5
    assert all(bucket.calls == 0 for bucket in report.buckets)
    assert report.totals is not None and report.totals.coverage.fraction == 1.0
