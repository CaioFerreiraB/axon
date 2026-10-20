"""Comparação com a linha de base (research R20; T029)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from axon_ai.eval.api import EvalReport, MetricValue
from axon_ai.eval.domain.compare import compare

pytestmark = pytest.mark.us3

AT = datetime(2026, 10, 7, 15, tzinfo=UTC)


def report(*metrics: MetricValue) -> EvalReport:
    return EvalReport(golden_set="g", assistant="a", started_at=AT, core_version="0", k=(5,), metrics=metrics)


def metric(name: str, value: float | None, *, det: bool = True, better: str | None = "higher") -> MetricValue:
    return MetricValue(name=name, value=value, n=3, deterministic=det, better=better)  # type: ignore[arg-type]


def deltas(
    current: EvalReport, base: EvalReport, tol: dict[str, float] | None = None
) -> dict[str, tuple[float | None, bool]]:
    return {d.name: (d.delta, d.regressed) for d in compare(current, base, tol or {}).deltas}


def test_regressao_alem_da_tolerancia_no_sentido_da_metrica() -> None:
    base = report(metric("recall@5", 0.9), metric("latency_ms_p50", 100.0, det=True, better="lower"))
    atual = report(metric("recall@5", 0.85), metric("latency_ms_p50", 101.0, det=True, better="lower"))
    resultado = deltas(atual, base)
    assert resultado["recall@5"][1] is True and resultado["recall@5"][0] == pytest.approx(-0.05)
    assert resultado["latency_ms_p50"][1] is True
    assert deltas(atual, base, {"recall@5": 0.1})["recall@5"][1] is False


def test_dentro_da_tolerancia_ou_melhor_nao_regride() -> None:
    base = report(metric("mrr", 0.5))
    assert deltas(report(metric("mrr", 0.49)), base)["mrr"][1] is False
    assert deltas(report(metric("mrr", 0.48)), base)["mrr"][1] is False, "0,02 exatos estão dentro"
    assert deltas(report(metric("mrr", 0.9)), base)["mrr"][1] is False


def test_so_deterministicas_barram() -> None:
    base = report(metric("faithfulness", 0.9, det=False))
    assert deltas(report(metric("faithfulness", 0.1, det=False)), base)["faithfulness"][1] is False
    informativa = report(metric("flag_rate:x", 0.9, det=True, better=None))
    assert deltas(report(metric("flag_rate:x", 0.0, det=True, better=None)), informativa)["flag_rate:x"][1] is False


def test_nova_ausente_e_sumida() -> None:
    base = report(metric("recall@5", 0.9), metric("mrr", 0.5))
    atual = report(metric("recall@5", None), metric("rerank_gain", 0.1))
    resultado = compare(atual, base, {})
    assert [(d.name, d.delta, d.regressed) for d in resultado.deltas] == [("recall@5", None, False)]
    assert resultado.missing == ("mrr",) and not resultado.regressed
