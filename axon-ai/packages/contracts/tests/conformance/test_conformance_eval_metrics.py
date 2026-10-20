"""Conformidade do hook opcional `eval_metrics` (ADR-027; spec 009 Fase 6, T020)."""

from __future__ import annotations

from typing import Any

import pytest
from packs import make_pack

from axon_ai_contracts import EvalItem, EvalObservation
from axon_ai_contracts.testing import check_pack


class Metric:
    def __init__(self, name: str = "m", better: Any = "higher", deterministic: Any = True) -> None:
        self.name = name
        self.better = better
        self.deterministic = deterministic

    def measure(self, item: EvalItem, observation: EvalObservation) -> float | None:
        return 1.0


class AsyncMetric(Metric):
    async def measure(self, item: EvalItem, observation: EvalObservation) -> float | None:  # type: ignore[override]
        return 1.0


def codes(pack: object) -> list[str]:
    return [issue.code for issue in check_pack(pack, check_distribution=False).issues]


def test_sem_metricas_nada_a_apontar() -> None:
    assert codes(make_pack()) == []


def test_metricas_validas() -> None:
    calls: list[int] = []

    def eval_metrics(self: Any, ctx: Any) -> tuple[Metric, ...]:
        calls.append(1)
        return (Metric("a"), Metric("b", better="lower", deterministic=False))

    assert codes(make_pack(eval_metrics=eval_metrics)) == []
    assert calls == [1], "hook de catálogo: chamado uma vez"


@pytest.mark.parametrize(
    ("metrics", "code"),
    [
        ("não é sequência", "hook.return_type"),
        ((object(),), "hook.return_type"),
        ((Metric(" "),), "eval_metric.name.invalid"),
        ((Metric("a"), Metric("a")), "eval_metric.duplicate_name"),
        ((Metric("a", better="maior"),), "eval_metric.contract"),
        ((Metric("a", deterministic="sim"),), "eval_metric.contract"),
        ((AsyncMetric("a"),), "eval_metric.contract"),
    ],
)
def test_metricas_fora_do_contrato(metrics: Any, code: str) -> None:
    assert codes(make_pack(eval_metrics=lambda self, ctx: metrics)) == [code]


def test_hook_que_levanta() -> None:
    def eval_metrics(self: Any, ctx: Any) -> Any:
        raise RuntimeError("quebrou")

    assert codes(make_pack(eval_metrics=eval_metrics)) == ["hook.raised"]
