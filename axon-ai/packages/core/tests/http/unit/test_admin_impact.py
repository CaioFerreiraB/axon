"""T130 — formato do impacto ambiental na administração (008 US12; research R64, R65). Puro."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from axon_ai.http.domain.admin_common import AdminInvalid
from axon_ai.http.domain.admin_impact import decimal_number, disabled_json, impact_json, impact_query
from axon_ai.observability.api import (
    ImpactBucket,
    ImpactCoverage,
    ImpactMetric,
    ImpactMetrics,
    ImpactQuery,
    ImpactReport,
    ImpactRow,
    ImpactTotals,
)

pytestmark = pytest.mark.us12

NOW = datetime(2026, 11, 3, 2, tzinfo=UTC)  # ainda dia 2 em São Paulo


def test_padroes_e_parametros() -> None:
    query = impact_query({}, now=NOW, default_tz="America/Sao_Paulo")
    assert (query.start, query.end, query.grain, query.by, query.origin) == (
        date(2026, 10, 4),
        date(2026, 11, 2),
        "day",
        "model",
        "production",
    )
    custom = impact_query(
        {"from": "2026-01-01", "to": "2026-06-30", "grain": "quarter", "by": "assistant", "origin": "all", "tz": "UTC"},
        now=NOW,
        default_tz="America/Sao_Paulo",
    )
    assert (custom.grain, custom.by, custom.origin, custom.tz) == ("quarter", "assistant", "all", "UTC")


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"grain": "day", "from": "2025-01-01", "to": "2026-03-01"}, "grain"),
        ({"from": "2026-10-10", "to": "2026-10-01"}, "from"),
        ({"grain": "ano"}, "grain"),
        ({"tz": "Lua/Base"}, "tz"),
        ({"pagina": "2"}, "pagina"),
    ],
)
def test_parametro_invalido(params: dict[str, str], field: str) -> None:
    with pytest.raises(AdminInvalid) as error:
        impact_query(params, now=NOW, default_tz="UTC")
    assert error.value.field == field


@pytest.mark.parametrize(
    ("value", "text"),
    [(3.2e-05, "0.000032"), (0.0, "0"), (123456789.0, "123457000"), (140.0, "140"), (1 / 3, "0.333333")],
)
def test_numero_decimal_sem_expoente(value: float, text: str) -> None:
    assert decimal_number(value) == text


def test_relatorio_e_desligado() -> None:
    query = ImpactQuery(start=date(2026, 10, 1), end=date(2026, 10, 31), tz="UTC", grain="month")
    metrics = ImpactMetrics(gwp_kgco2eq=ImpactMetric(0.0001, 0.0003))
    coverage = ImpactCoverage(calls=3, eligible=2, estimated=1, approximate=1)
    row = ImpactRow(
        key="openrouter/z-ai/glm-5.3-flash",
        impact_model="mistralai/zai-glm-5-3",
        match="approximate",
        calls=3,
        responses=2,
        estimated_responses=1,
        estimated_output_tokens=40,
        coverage=coverage,
        metrics=metrics,
    )
    report = ImpactReport(
        query=query,
        version="0.11.3",
        buckets=(ImpactBucket(start=date(2026, 10, 1), end=date(2026, 10, 31), calls=3, metrics=metrics, rows=(row,)),),
        rows=(row,),
        totals=ImpactTotals(metrics=metrics, coverage=coverage, responses=2, trees=0.0000014),
        clipped_start=date(2026, 10, 1),
    )
    body = impact_json(report)
    assert body["enabled"] is True and body["clipped_from"] == "2026-10-01"
    assert body["method"] == {"ecologits_version": "0.11.3", "tree_kg_co2e": "140", "tree_years": 20}
    assert body["rows"][0]["metrics"]["gwp_kgco2eq"] == {"min": "0.0001", "max": "0.0003", "mean": "0.0002"}
    assert body["rows"][0]["coverage"]["unestimated"] == 1
    assert body["totals"]["trees"] == "0.0000014"
    assert body["previous_totals"] is None
    assert body["buckets"][0]["start"] == "2026-10-01" and body["buckets"][0]["rows"][0]["match"] == "approximate"

    off = disabled_json(query)
    assert (off["enabled"], off["totals"], off["previous_totals"], off["buckets"], off["rows"]) == (
        False,
        None,
        None,
        [],
        [],
    )
    assert off["method"]["ecologits_version"] is None
