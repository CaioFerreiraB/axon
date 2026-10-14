"""A timeline de status do Open WebUI (`domain/timeline.py`; FR-005a, research R42): puro, tempo dado pelo teste."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_core.graph.api import (
    CatalogOutcome,
    ControllerOutcome,
    ExecutionIssue,
    FinalEvent,
    GateOutcome,
    GenerationOutcome,
    ProgressEvent,
    RerankOutcome,
    SourceRef,
    StepFinished,
    ToolCallsOutcome,
    ToolCallSummary,
)
from ai_core.http.domain.timeline import (
    ARGUMENTS_LIMIT,
    Status,
    Timeline,
    duration,
    outcome_lines,
)
from ai_core_contracts import Citation

pytestmark = pytest.mark.us6

T0 = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def search(*sources: SourceRef, status: str = "ok", truncated: bool = False) -> ToolCallSummary:
    return ToolCallSummary(
        tool="scouting.search_docs",
        kind="retrieval",
        arguments={"query": "o que é escotismo?", "top_k": 20},
        status=status,
        truncated=truncated,
        sources=sources,
    )


# --- início e fim de etapa, com o tempo ------------------------------------------------------------------------


def test_inicio_reaproveita_a_linha_de_progresso_e_fica_aberto() -> None:
    timeline = Timeline(T0)
    assert timeline.started(ProgressEvent(stage="retrieve"), at(0)) == Status("Consultando os documentos…", done=False)


def test_fim_traz_o_desfecho_e_o_tempo_desde_o_inicio() -> None:
    timeline = Timeline(T0)
    timeline.started(ProgressEvent(stage="prepare_context"), at(0))
    assert timeline.finished(StepFinished(stage="prepare_context"), at(0.3)) == (
        Status("Contexto preparado · 300 ms", done=True),
    )


def test_fim_sem_inicio_sai_sem_tempo_e_inicio_nao_vaza_para_a_iteracao_seguinte() -> None:
    timeline = Timeline(T0)
    timeline.started(ProgressEvent(stage="controller", detail="iteração 1"), at(0))
    decided = StepFinished(stage="controller", outcome=ControllerOutcome(iteration=1, action="answer", model="p/m"))
    assert timeline.finished(decided, at(1.2))[0].description.endswith(" · 1,2 s")
    assert timeline.finished(decided, at(9))[0].description == "Decisão (iteração 1, p/m): responder"


def test_varias_chamadas_uma_linha_cada_e_o_tempo_na_ultima() -> None:
    timeline = Timeline(T0)
    timeline.started(ProgressEvent(stage="retrieve"), at(0))
    other = ToolCallSummary(tool="docs.search", kind="retrieval", arguments={"query": "q"}, status="ok")
    lines = timeline.finished(StepFinished(stage="retrieve", outcome=ToolCallsOutcome(calls=(search(), other))), at(2))
    assert [line.description.endswith(" · 2,0 s") for line in lines] == [False, True]


def test_etapa_desconhecida_tem_linha_generica() -> None:
    assert outcome_lines("nova", None) == ["Etapa nova concluída"]


# --- desfechos ------------------------------------------------------------------------------------------------


def test_busca_nomeia_argumentos_trechos_e_documentos_sem_repetir() -> None:
    sources = (
        SourceRef(document="POR 2025", section="Regra 1", page=3),
        SourceRef(document="POR 2025", section="Regra 2"),
        SourceRef(document="Estatuto 2024"),
        SourceRef(document="Resolução 08/2021"),
        SourceRef(document="Escotistas em Ação"),
    )
    (line,) = outcome_lines("retrieve", ToolCallsOutcome(calls=(search(*sources),)))
    assert line == (
        'scouting.search_docs(query="o que é escotismo?", top_k=20) → ok: 5 trechos de 4 documentos: '
        "POR 2025, Estatuto 2024, Resolução 08/2021 e mais 1"
    )


def test_busca_sem_resultado_e_com_falha() -> None:
    (vazia,) = outcome_lines("retrieve", ToolCallsOutcome(calls=(search(),)))
    assert vazia.endswith("→ ok: nenhum trecho")
    (falha,) = outcome_lines("retrieve", ToolCallsOutcome(calls=(search(status="timeout"),)))
    assert falha.endswith("→ tempo esgotado")


def test_tool_comum_mostra_status_e_corte() -> None:
    call = ToolCallSummary(tool="crm.buscar", kind="mcp", arguments={"nome": "Ana"}, status="ok", truncated=True)
    assert outcome_lines("execute_tool", ToolCallsOutcome(calls=(call,))) == ['crm.buscar(nome="Ana") → ok, cortado']
    unknown = ToolCallSummary(tool="x.y", status="unknown")
    assert outcome_lines("execute_tool", ToolCallsOutcome(calls=(unknown,))) == ["x.y() → ferramenta inexistente"]


def test_argumentos_longos_sao_cortados() -> None:
    call = ToolCallSummary(tool="t.x", arguments={"texto": "a" * 500}, status="ok")
    (line,) = outcome_lines("execute_tool", ToolCallsOutcome(calls=(call,)))
    arguments = line[len("t.x(") : line.index(") →")]
    assert len(arguments) == ARGUMENTS_LIMIT and arguments.endswith("…")


def test_rerank_lista_as_fontes_mantidas_e_o_reranker_que_falhou() -> None:
    kept = (
        SourceRef(document="POR", section="Regra 12", page=34),
        SourceRef(document="Estatuto", section="Art. 3º", page=2),
        SourceRef(document="POR"),
        SourceRef(document="Manual", page=7),
    )
    assert outcome_lines("rerank", RerankOutcome(candidates=20, kept=kept)) == [
        "4 de 20 trechos: POR — Regra 12, p. 34; Estatuto — Art. 3º, p. 2; POR e mais 1"
    ]
    assert outcome_lines("rerank", RerankOutcome(candidates=1, kept=kept[:1], degraded=("docs",))) == [
        "1 de 1 trecho: POR — Regra 12, p. 34 (reranker de docs falhou; valeu a ordem da busca)"
    ]
    assert outcome_lines("rerank", RerankOutcome(candidates=0)) == ["Nenhum trecho para ordenar"]


@pytest.mark.parametrize(
    ("gate", "line"),
    [
        (
            GateOutcome(covered=True, route="generate", best_score=0.893, delivered=5),
            "Coberto: melhor score 0,89, sem limiar → resposta com 5 trechos",
        ),
        (
            GateOutcome(covered=True, route="generate", best_score=0.9, threshold=0.8, delivered=1),
            "Coberto: melhor score 0,90, limiar 0,80 → resposta com 1 trecho",
        ),
        (
            GateOutcome(covered=False, route="controller", best_score=0.62, threshold=0.8),
            "Não coberto: melhor score 0,62 abaixo do limiar 0,80 → busca com ferramentas",
        ),
        (GateOutcome(covered=False, route="fallback"), "Não coberto: nenhum trecho → resposta sem trechos"),
    ],
)
def test_portao(gate: GateOutcome, line: str) -> None:
    assert outcome_lines("gate", gate) == [line]


@pytest.mark.parametrize(
    ("decision", "what"),
    [
        (
            ControllerOutcome(iteration=1, action="tool", model="openai/gpt", tool="t.x", arguments={"q": 1}),
            "chamar t.x(q=1)",
        ),
        (ControllerOutcome(iteration=2, action="answer", model="openai/gpt"), "responder"),
        (
            ControllerOutcome(iteration=1, action="invalid", model="openai/gpt", reason="JSON malformado"),
            "ação inválida (JSON malformado)",
        ),
        (
            ControllerOutcome(iteration=1, action="failed", model="openai/gpt", reason="ModelCallFailed"),
            "o controller falhou; segue para a resposta",
        ),
    ],
)
def test_decisao_do_controller(decision: ControllerOutcome, what: str) -> None:
    assert outcome_lines("controller", decision) == [f"Decisão (iteração {decision.iteration}, openai/gpt): {what}"]


def test_geracao_com_e_sem_tokens() -> None:
    assert outcome_lines("generate", GenerationOutcome(model="p/m", input_tokens=1840, output_tokens=312)) == [
        "Resposta de p/m · 1.840 tokens de entrada, 312 de saída"
    ]
    assert outcome_lines("generate", GenerationOutcome(model="p/m")) == ["Resposta de p/m"]


def test_catalogo() -> None:
    assert outcome_lines("load_capabilities", CatalogOutcome(tools=7, unavailable=("crm",))) == [
        "7 ferramentas disponíveis; indisponível: crm"
    ]
    assert outcome_lines("load_capabilities", CatalogOutcome(tools=1)) == ["1 ferramenta disponível"]
    assert outcome_lines("load_capabilities", CatalogOutcome(tools=0)) == ["Nenhuma ferramenta disponível"]


# --- fim da execução ------------------------------------------------------------------------------------------


def test_fim_com_avisos_e_citacoes() -> None:
    final = FinalEvent(
        answer="ok",
        citations=(Citation(chunk_id="a", document="POR"), Citation(chunk_id="b", document="POR")),
        errors=(ExecutionIssue(stage="gate", kind="ContextTrimmed", message="1 trecho tirado", severity="notice"),),
    )
    assert Timeline(T0).final(final, at(21)) == (
        Status("Aviso: 1 trecho tirado", done=True),
        Status("Concluído em 21 s · 2 citações", done=True),
    )


def test_fim_com_erro_mostra_o_tipo_e_nunca_a_mensagem() -> None:
    final = FinalEvent(
        answer="",
        errors=(ExecutionIssue(stage="retrieve", kind="RetrievalFailed", message="tool 'x': SEGREDO 10.0.0.5"),),
    )
    lines = [status.description for status in Timeline(T0).final(final, at(1.5))]
    assert lines == ["Erro em retrieve: RetrievalFailed", "Terminou com erro em 1,5 s"]


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0.012, "12 ms"), (1.24, "1,2 s"), (18.4, "18 s"), (59.6, "1 min"), (63, "1 min 3 s")],
)
def test_duracao(seconds: float, text: str) -> None:
    assert duration(timedelta(seconds=seconds)) == text
