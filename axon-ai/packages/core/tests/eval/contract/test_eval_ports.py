"""Conformidade das portas de arquivo do harness, contra memória e arquivo (research R26; T030, T031)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from axon_ai.eval.adapters.files import JsonReportStore, YamlGoldenSetSource
from axon_ai.eval.adapters.memory import InMemoryBaselineStore, InMemoryGoldenSetSource
from axon_ai.eval.api import EvalInputError, EvalReport, GoldenSetError, InvalidItem, ItemResult, MetricValue
from axon_ai.eval.domain.golden import parse_golden

pytestmark = pytest.mark.us2

AT = datetime(2026, 10, 7, 15, tzinfo=UTC)
YAML = """
version: 1
name: exemplo
assistant: docs
items:
  - id: q001
    question: "Quem pode ser patrono?"
    reference_time: "2026-10-07T12:00:00-03:00"
    expected_documents:
      - document: Regulamento
        section: Regra 31
  - id: ruim
    question: ""
    reference_time: "2026-10-07T12:00:00-03:00"
"""

REPORT = EvalReport(
    golden_set="exemplo",
    assistant="docs",
    judge="teste/juiz",
    started_at=AT,
    core_version="0.3.0",
    k=(5, 20),
    metrics=[
        MetricValue(name="recall@5", value=0.8, n=2, deterministic=True, better="higher"),
        MetricValue(name="faithfulness", value=0.7, variance=0.01, n=2, deterministic=False, better="higher"),
        MetricValue(name="gate_route:generate", value=1.0, n=2, deterministic=False, better=None),
    ],
    items=[
        ItemResult(
            id="q001",
            metrics={"recall@5": 1.0, "faithfulness": None},
            citations=[{"chunk_id": "c1", "document": "D", "page": 3}],
            flags=["ungrounded"],
            issue_kinds=["CoverageInsufficient"],
            gate_route="generate",
            warnings=["evidência não vista: X"],
        ),
        ItemResult(id="q002", failure="Assistant indisponível"),
    ],
    invalid=[InvalidItem(id="ruim", reason="question vazia ou ausente")],
    annotations=["RAM 6 GB"],
)


@pytest.fixture(params=["memoria", "arquivo"])
def golden_source(request: Any, tmp_path: Path) -> tuple[Any, Path]:
    path = tmp_path / "golden.yaml"
    if request.param == "memoria":
        import yaml

        return InMemoryGoldenSetSource({path: parse_golden(yaml.safe_load(YAML))}), path
    path.write_text(YAML, encoding="utf-8")
    return YamlGoldenSetSource(), path


def test_conjunto_dourado_lido(golden_source: tuple[Any, Path]) -> None:
    source, path = golden_source
    conjunto = source.load(path)
    assert (conjunto.name, conjunto.assistant, [i.id for i in conjunto.items]) == ("exemplo", "docs", ["q001"])
    assert [i.id for i in conjunto.invalid] == ["ruim"]


def test_conjunto_ilegivel(tmp_path: Path) -> None:
    with pytest.raises(GoldenSetError):
        YamlGoldenSetSource().load(tmp_path / "nao-existe.yaml")
    ruim = tmp_path / "ruim.yaml"
    ruim.write_text("items: [", encoding="utf-8")
    with pytest.raises(GoldenSetError):
        YamlGoldenSetSource().load(ruim)
    with pytest.raises(GoldenSetError):
        InMemoryGoldenSetSource().load(ruim)


@pytest.fixture(params=["memoria", "arquivo"])
def store(request: Any) -> Any:
    return InMemoryBaselineStore() if request.param == "memoria" else JsonReportStore()


def test_relatorio_ida_e_volta(store: Any, tmp_path: Path) -> None:
    path = tmp_path / "base" / "relatorio.json"
    assert store.load(path) is None
    store.save(path, REPORT)
    assert store.load(path) == REPORT


def test_relatorio_em_formato_desconhecido(tmp_path: Path) -> None:
    path = tmp_path / "r.json"
    path.write_text('{"version": 9}', encoding="utf-8")
    with pytest.raises(EvalInputError, match="version"):
        JsonReportStore().load(path)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(EvalInputError):
        JsonReportStore().load(path)
