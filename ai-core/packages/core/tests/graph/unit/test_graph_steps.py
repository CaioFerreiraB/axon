"""Montagem do desfecho de etapa (`domain/steps.py`, ADR-028): pura, sem texto de trecho nem de erro."""

from __future__ import annotations

from graph_testkit import chunk

from ai_core.capabilities.api import FencedToolResult, ToolCall
from ai_core.graph.api import SourceRef, ToolCallSummary
from ai_core.graph.domain.steps import source_refs, tool_summary


def test_fontes_na_ordem_sem_texto() -> None:
    chunks = (chunk("a", document="POR", section="Regra 1", page=2), chunk("b", document="Estatuto"))
    assert source_refs(chunks) == (
        SourceRef(document="POR", section="Regra 1", page=2),
        SourceRef(document="Estatuto"),
    )


def test_resumo_da_chamada_leva_pedido_e_status_e_deixa_texto_e_erro_de_fora() -> None:
    call = ToolCall(name="docs.search", arguments={"query": "q", "top_k": 5})
    result = FencedToolResult(
        name="docs.search",
        kind="retrieval",
        status="error",
        text="<tool_result>conteúdo</tool_result>",
        truncated=True,
        error="detalhe interno",
        chunks=(chunk("a", document="POR"),),
    )
    assert tool_summary(call, result) == ToolCallSummary(
        tool="docs.search",
        kind="retrieval",
        arguments={"query": "q", "top_k": 5},
        status="error",
        truncated=True,
        sources=(SourceRef(document="POR"),),
    )
