"""Métricas do core por item, agregação e leitura do trace (research R15, R17; T027). Puras, por tabela."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from ai_core.eval.api import Evidence, GoldenItem
from ai_core.eval.domain.metrics import (
    MetricSpec,
    ModelCallSample,
    Operation,
    aggregate,
    citation_metrics,
    core_specs,
    operation_metrics,
    percentile,
    retrieval_metrics,
    shares,
    unseen_evidence,
)
from ai_core.eval.domain.observation import observe, operation
from ai_core.graph.api import ExecutionIssue, FinalEvent
from ai_core.observability.api import TraceRecord
from ai_core_contracts import EvalChunk, EvalObservation

pytestmark = pytest.mark.us2

AT = datetime(2026, 10, 7, 15, tzinfo=UTC)


def item(*documents: str, citations: tuple[str, ...] = ()) -> GoldenItem:
    return GoldenItem(
        id="q001",
        question="pergunta",
        reference_time=AT,
        expected_documents=[Evidence(document=d) for d in documents],
        expected_citations=[Evidence(document=d) for d in citations],
    )


def chunk(chunk_id: str, document: str) -> EvalChunk:
    return EvalChunk(chunk_id=chunk_id, score=0.5, document=document)


RETRIEVED = (chunk("x1", "X"), chunk("a1", "A"), chunk("y1", "Y"), chunk("b1", "B"), chunk("z1", "Z"))


def test_recall_mrr_e_entregues() -> None:
    observacao = EvalObservation(answer="", retrieved=RETRIEVED, delivered=RETRIEVED[:2])
    metricas = retrieval_metrics(item("A", "B"), observacao, (1, 2, 5))
    assert (metricas["recall@1"], metricas["recall@2"], metricas["recall@5"]) == (0.0, 0.5, 1.0)
    assert metricas["mrr"] == 0.5
    assert metricas["delivered_recall"] == 0.5
    assert metricas["rerank_gain"] is None, "sem rerank, sem ganho"


def test_ganho_do_rerank() -> None:
    reordenados = (chunk("a1", "A"), chunk("b1", "B"))
    observacao = EvalObservation(answer="", retrieved=RETRIEVED, reranked=reordenados)
    assert retrieval_metrics(item("A", "B"), observacao, (5,))["rerank_gain"] == 0.5  # 2/2 contra 1/2 nos 2 primeiros


def test_item_sem_evidencia_fica_fora_e_nada_recuperado_conta_zero() -> None:
    sem = retrieval_metrics(item(), EvalObservation(answer="", retrieved=RETRIEVED), (5,))
    assert set(sem.values()) == {None}
    vazio = retrieval_metrics(item("A"), EvalObservation(answer=""), (5,))
    assert (vazio["recall@5"], vazio["mrr"], vazio["delivered_recall"]) == (0.0, 0.0, 0.0)


def test_citacoes() -> None:
    observacao = EvalObservation(
        answer="",
        citations=[{"chunk_id": "a1", "document": "A"}, {"chunk_id": "fora", "document": "B"}],
        delivered=(chunk("a1", "A"),),
    )
    metricas = citation_metrics(item(citations=("A", "C")), observacao)
    assert metricas == {
        "citation_resolvable_rate": 0.5,
        "citation_invented_rate": 0.5,
        "expected_citation_recall": 0.5,
    }
    sem = citation_metrics(item(), EvalObservation(answer=""))
    assert set(sem.values()) == {None}


def test_operacao() -> None:
    calls = (
        ModelCallSample(role="controller", input_tokens=50, output_tokens=5, duration_ms=200.0),
        ModelCallSample(role="generation", input_tokens=100, output_tokens=40, duration_ms=2000.0),
    )
    metricas = operation_metrics(
        Operation(latency_ms=2500.0, ttft_ms=300.0, model_calls=calls, decisions=("tool", "invalid", "answer"))
    )
    assert metricas["tokens_per_answer"] == 195.0 and metricas["model_calls_per_answer"] == 2.0
    assert metricas["generation_tokens_per_s"] == 20.0
    assert metricas["controller_invalid_rate"] == pytest.approx(1 / 3)
    assert (metricas["latency_ms"], metricas["ttft_ms"], metricas["error_rate"]) == (2500.0, 300.0, 0.0)
    assert operation_metrics(Operation(latency_ms=1.0, has_error=True))["error_rate"] == 1.0


def test_agregacao_media_e_percentis() -> None:
    specs = (
        MetricSpec(name="recall@5", better="higher", deterministic=True),
        MetricSpec(name="latency_ms", better="lower", deterministic=False, aggregate="percentiles"),
    )
    per_item: list[dict[str, Any]] = [
        {"recall@5": 1.0, "latency_ms": 100.0},
        {"recall@5": None, "latency_ms": 300.0},
        {"recall@5": 0.5, "latency_ms": 200.0},
    ]
    agregadas = {m.name: m for m in aggregate(specs, per_item)}
    assert (agregadas["recall@5"].value, agregadas["recall@5"].n, agregadas["recall@5"].deterministic) == (
        0.75,
        2,
        True,
    )
    assert agregadas["latency_ms_p50"].value == 200.0 and agregadas["latency_ms_p95"].value == 300.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert aggregate(specs[:1], [{}])[0].value is None


def test_especificacoes_do_core() -> None:
    nomes = {spec.name: spec for spec in core_specs((5, 20))}
    assert {"recall@5", "recall@20", "mrr", "delivered_recall", "rerank_gain"} <= set(nomes)
    deterministicas = {name for name, spec in nomes.items() if spec.deterministic}
    assert deterministicas == {"recall@5", "recall@20", "mrr", "delivered_recall", "rerank_gain"}
    assert nomes["citation_invented_rate"].better == "lower"


def test_fracoes_informativas() -> None:
    fracoes = {m.name: m for m in shares("flag_rate", [["ungrounded"], [], ["ungrounded", "x"]], 3)}
    assert fracoes["flag_rate:ungrounded"].value == pytest.approx(2 / 3)
    assert fracoes["flag_rate:x"].better is None and not fracoes["flag_rate:x"].deterministic


def test_evidencia_nao_vista() -> None:
    itens = [item("A", "Inexistente")]
    avisos = unseen_evidence(itens, [RETRIEVED])
    assert avisos == {"q001": ["evidência não vista: Inexistente"]}


def record(type_: str, **attributes: Any) -> TraceRecord:
    return TraceRecord(at=AT, type=type_, request_id="r", attributes=attributes)


def test_observacao_e_operacao_a_partir_do_trace() -> None:
    final = FinalEvent(
        answer="Resposta [1].",
        citations=({"chunk_id": "a1", "document": "A"},),
        errors=(ExecutionIssue(stage="gate", kind="CoverageInsufficient", message="m", severity="notice"),),
        flags=frozenset({"ungrounded"}),
    )
    records = [
        record("model_call", role="generation", provider="p", model="m", duration_ms=1000.0, output_tokens=10),
        record("controller_decision", iteration=1, action="invalid", reason="JSON malformado"),
        record("coverage_gate", candidates=2, passages=1, covered=True, route="generate"),
        record(
            "retrieval",
            retrieved=[
                {"chunk_id": "a1", "score": 0.9, "document": "A", "page": 3},
                {"chunk_id": "b1", "score": 0.1, "document": "B"},
            ],
            delivered=[{"chunk_id": "a1", "score": 0.9, "document": "A", "page": 3}],
        ),
    ]
    observacao = observe(final, records)
    assert [c.chunk_id for c in observacao.retrieved] == ["a1", "b1"] and observacao.reranked == ()
    assert observacao.delivered[0].page == 3 and observacao.issue_kinds == ("CoverageInsufficient",)
    custo = operation(final, records, latency_ms=1200.0, ttft_ms=400.0)
    assert (custo.gate_route, custo.decisions, custo.has_error) == ("generate", ("invalid",), False)
    assert custo.model_calls[0].output_tokens == 10
    assert observe(final, []).retrieved == ()
    assert operation(None, [], latency_ms=1.0, ttft_ms=None).has_error
