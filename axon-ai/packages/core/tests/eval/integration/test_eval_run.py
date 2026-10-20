"""US2 — medir com um conjunto dourado (contracts/eval-harness.md, verificações 1, 2, 6 e 7; Edge Case "documento
fora do corpus"; T032). Plataforma real no perfil `test`, com um pack de teste e um gerador que cita."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from eval_testkit import PRINCIPAL, Observed, eval_platform, harness

from axon_ai.eval.adapters.memory import ScriptedJudge
from axon_ai.eval.api import EvalInputError
from axon_ai.eval.domain.golden import parse_golden
from axon_ai.eval.ports import Judgement

pytestmark = pytest.mark.us2

BRT = timezone(timedelta(hours=-3))
GOLDEN = {
    "version": 1,
    "name": "teste",
    "k": [1, 5],
    "items": [
        {
            "id": "q001",
            "question": "Quem pode ser patrono?",
            "reference_time": "2026-10-07T12:00:00-03:00",
            "expected_documents": [{"document": "Regulamento", "section": "Regra 31"}],
            "expected_citations": [{"document": "Regulamento"}],
            "reference_answer": "Uma pessoa inspiradora já falecida.",
        },
        {
            "id": "q002",
            "question": "Qual a faixa etária?",
            "reference_time": "2025-03-01T09:00:00-03:00",
            "expected_documents": [{"document": "manual"}],
        },
        {
            "id": "q003",
            "question": "E o documento que não existe?",
            "reference_time": "2026-10-07T12:00:00-03:00",
            "expected_documents": [{"document": "Inexistente"}],
        },
        {"id": "ruim", "question": "", "reference_time": "2026-10-07T12:00:00-03:00"},
    ],
}


async def test_relatorio_com_todas_as_metricas(tmp_path: Path) -> None:
    observed = Observed()
    plataforma = eval_platform(tmp_path, observed)
    try:
        report = await harness(plataforma).run(parse_golden(GOLDEN), assistant="docs", principal=PRINCIPAL)
    finally:
        plataforma.aclose()

    assert [i.id for i in report.invalid] == ["ruim"]
    assert [item.id for item in report.items] == ["q001", "q002", "q003"]
    assert all(item.failure is None for item in report.items)
    metricas = {m.name: m for m in report.metrics}
    assert metricas["recall@1"].value == pytest.approx(1 / 3) and metricas["recall@5"].value == pytest.approx(2 / 3)
    assert metricas["mrr"].value == pytest.approx((1 + 0.5 + 0) / 3)
    for nome in (
        "delivered_recall",
        "rerank_gain",
        "citation_resolvable_rate",
        "citation_invented_rate",
        "expected_citation_recall",
        "latency_ms_p50",
        "latency_ms_p95",
        "ttft_ms_p50",
        "tokens_per_answer",
        "model_calls_per_answer",
        "error_rate",
    ):
        assert metricas[nome].value is not None, nome
    assert metricas["citation_resolvable_rate"].value == 1.0 and metricas["citation_invented_rate"].value == 0.0
    assert metricas["recall@5"].deterministic and not metricas["latency_ms_p50"].deterministic
    assert metricas["docs:current_rate"].value == pytest.approx(2 / 3) and metricas["docs:current_rate"].deterministic
    assert metricas["gate_route:generate"].value == 1.0
    assert metricas["faithfulness"].value is None and metricas["coverage"].value is None, "sem juiz: ausentes"
    assert observed.reference_times == [
        datetime(2026, 10, 7, 15, tzinfo=UTC),
        datetime(2025, 3, 1, 12, tzinfo=UTC),
        datetime(2026, 10, 7, 15, tzinfo=UTC),
    ], "a data de cada item chega à preparação (ADR-013)"
    q003 = report.items[2]
    assert q003.warnings == ("evidência não vista: Inexistente",)
    assert report.items[0].citations[0]["chunk_id"] == "reg#r31@p37"


async def test_juiz_media_e_variancia(tmp_path: Path) -> None:
    juiz = ScriptedJudge(
        [
            Judgement(faithfulness=1.0, coverage=1.0),
            Judgement(faithfulness=0.5, coverage=0.5),
            Judgement(faithfulness=0.0, coverage=None),
        ]
        * 3
    )
    plataforma = eval_platform(tmp_path, Observed())
    try:
        report = await harness(plataforma, judge=juiz).run(parse_golden(GOLDEN), assistant="docs", principal=PRINCIPAL)
    finally:
        plataforma.aclose()
    metricas = {m.name: m for m in report.metrics}
    assert report.judge == "teste/juiz"
    assert metricas["faithfulness"].value == pytest.approx(0.5) and metricas["faithfulness"].variance == pytest.approx(
        1 / 6
    )
    assert metricas["coverage"].value == pytest.approx(0.75) and metricas["coverage"].n == 1, "só o item com referência"
    primeiro = juiz.calls[0]
    assert primeiro["passages"] == [
        "Patrono: pessoa inspiradora falecida.",
        "O ramo atende de 6,5 a 10 anos.",
        "Regra antiga sobre faixas etárias.",
    ]
    assert primeiro["reference"] == "Uma pessoa inspiradora já falecida." and str(primeiro["id"]).endswith(":judge:1")
    assert len(juiz.calls) == 9


async def test_assistant_inexistente_e_entrada_invalida(tmp_path: Path) -> None:
    plataforma = eval_platform(tmp_path, Observed())
    try:
        with pytest.raises(EvalInputError, match="nao-existe"):
            await harness(plataforma).run(parse_golden(GOLDEN), assistant="nao-existe", principal=PRINCIPAL)
    finally:
        plataforma.aclose()
