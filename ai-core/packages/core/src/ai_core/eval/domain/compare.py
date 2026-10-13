"""Comparação com a linha de base — pura (FR-007; research R20).

Regressão = a métrica piorou além da tolerância, no sentido em que ela melhora, e é determinística. As julgadas por
modelo e as de operação aparecem com o delta, mas nunca barram sozinhas (US3 cen. 2).
"""

from __future__ import annotations

from collections.abc import Mapping

from ai_core.eval.api import DEFAULT_TOLERANCE, Comparison, EvalReport, MetricDelta


def compare(current: EvalReport, baseline: EvalReport, tolerances: Mapping[str, float]) -> Comparison:
    deltas: list[MetricDelta] = []
    for metric in current.metrics:
        base = baseline.metric(metric.name)
        if base is None:
            continue  # métrica nova: não regride
        tolerance = tolerances.get(metric.name, DEFAULT_TOLERANCE)
        if metric.value is None or base.value is None:
            deltas.append(
                MetricDelta(
                    name=metric.name,
                    baseline=base.value,
                    current=metric.value,
                    delta=None,
                    tolerance=tolerance,
                    regressed=False,
                )
            )
            continue
        delta = metric.value - base.value
        worse = -delta if metric.better == "higher" else delta if metric.better == "lower" else 0.0
        deltas.append(
            MetricDelta(
                name=metric.name,
                baseline=base.value,
                current=metric.value,
                delta=delta,
                tolerance=tolerance,
                regressed=metric.deterministic and worse > tolerance + 1e-12,
            )
        )
    present = {metric.name for metric in current.metrics}
    missing = tuple(metric.name for metric in baseline.metrics if metric.name not in present)
    return Comparison(deltas=deltas, missing=missing)
