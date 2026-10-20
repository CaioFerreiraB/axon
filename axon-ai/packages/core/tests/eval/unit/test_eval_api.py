"""Seam do harness (spec 009 Fase 6; data-model "Harness"; T024): conjunto dourado, relatório e comparação."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

import axon_ai.eval.api as api
from axon_ai.eval.api import (
    Comparison,
    EvalReport,
    Evidence,
    GoldenItem,
    GoldenSet,
    InvalidItem,
    ItemResult,
    MetricDelta,
    MetricValue,
)

pytestmark = pytest.mark.us2

AT = datetime(2026, 10, 7, 15, tzinfo=UTC)


def item(**changes: Any) -> GoldenItem:
    return GoldenItem(**({"id": "q001", "question": "Quem pode ser patrono?", "reference_time": AT} | changes))


def test_evidencia_exige_documento() -> None:
    assert Evidence(document="Regulamento").section is None
    with pytest.raises(ValueError, match="document"):
        Evidence(document="")


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"id": "Q 1"}, "id"),
        ({"id": ""}, "id"),
        ({"question": " "}, "question"),
        ({"reference_time": datetime(2026, 10, 7)}, "reference_time"),
    ],
)
def test_item_invalido(changes: dict[str, Any], field: str) -> None:
    with pytest.raises(ValueError, match=field):
        item(**changes)


def test_item_congela() -> None:
    criado = item(expected_documents=[Evidence(document="D")], extra={"a": [1]})
    assert criado.expected_documents == (Evidence(document="D"),)
    with pytest.raises(TypeError):
        criado.extra["b"] = 2  # type: ignore[index]


def test_conjunto() -> None:
    conjunto = GoldenSet(name="g", items=[item(), item(id="q002")])
    assert (conjunto.k, conjunto.assistant, conjunto.invalid) == ((5, 20), None, ())
    for changes in ({"name": ""}, {"k": ()}, {"k": (0,)}, {"tolerances": {"recall@5": -0.1}}):
        with pytest.raises(ValueError):
            GoldenSet(**({"name": "g", "items": [item()]} | changes))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="q001"):
        GoldenSet(name="g", items=[item(), item()])


def test_relatorio_e_comparacao() -> None:
    metrica = MetricValue(name="recall@5", value=0.8, n=3, deterministic=True, better="higher")
    resultado = ItemResult(id="q001", metrics={"recall@5": 0.8})
    relatorio = EvalReport(
        golden_set="g",
        assistant="docs",
        started_at=AT,
        core_version="0.3.0",
        k=(5, 20),
        metrics=[metrica],
        items=[resultado],
        invalid=[InvalidItem(id="q9", reason="question vazia")],
        annotations=["RAM 6 GB"],
    )
    assert relatorio.metric("recall@5") == metrica and relatorio.metric("mrr") is None
    assert relatorio.judge is None and resultado.warnings == () and resultado.failure is None
    delta = MetricDelta(name="recall@5", baseline=0.9, current=0.8, delta=-0.1, tolerance=0.02, regressed=True)
    assert Comparison(deltas=[delta]).regressed and not Comparison(deltas=()).regressed


def test_informativa_sem_sentido() -> None:
    assert MetricValue(name="gate_route:generate", value=0.5, n=2, deterministic=False, better=None).better is None
    with pytest.raises(ValueError, match="better"):
        MetricValue(name="x", value=1.0, n=1, deterministic=False, better="maior")  # type: ignore[arg-type]


def test_nomes_publicos() -> None:
    public = {name for name in vars(api) if not name.startswith("_")}
    expected = {
        "Better",
        "Comparison",
        "EvalHarness",
        "EvalInputError",
        "EvalReport",
        "Evidence",
        "GoldenItem",
        "GoldenSet",
        "GoldenSetError",
        "InvalidItem",
        "ItemResult",
        "MetricDelta",
        "MetricValue",
        "DEFAULT_K",
        "DEFAULT_TOLERANCE",
    }
    assert expected <= public
