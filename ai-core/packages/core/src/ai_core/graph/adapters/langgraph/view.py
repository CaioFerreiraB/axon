"""Projeção do estado interno na Turn View do contrato 001 (ADR-011).

Manter a projeção num arquivo só é o que permite reescrever o estado sem tocar em pack nenhum. As fatias por pack
(`own_slice`, `dependency_slices`) são recortadas pela 002 a partir do mapa de fatias — este módulo entrega a visão
global e o mapa.
"""

from __future__ import annotations

from ai_core.graph.adapters.langgraph.state import AgentState
from ai_core.graph.domain.transcript import ToolStep
from ai_core_contracts import Chunk, ToolResult, TurnView


def turn_view(state: AgentState) -> TurnView:
    """Visão somente-leitura da execução, como os hooks de pack a enxergam.

    No `chat` não há retrieval nem tools, então `retrieved`, `reranked`, `generation_context` e `tool_results` ficam
    vazios — `generation_context` é o campo que os validators leem para verificar citação (ADR-007), e vazio é a
    resposta correta para um flow que não entrega chunk nenhum à geração.

    No `agentic` (research R26), `tool_results` são os resultados **entregues à geração**, na ordem — sem os omitidos
    pelo teto, que são sempre os mais antigos; `retrieved` são os chunks de todos os resultados de recuperação, e
    `generation_context`, os dos que ficaram. O `agentic` não reordena: `reranked` fica vazio.
    """
    executed = [step for step in state.get("steps", ()) if isinstance(step, ToolStep)]
    delivered = executed[state.get("omitted", 0) :]
    return TurnView(
        request_id=state["request_id"],
        assistant=state["assistant"],
        reference_time=state["reference_time"],
        question=state["question"],
        messages=state.get("messages", ()),
        retrieved=_chunks(executed),
        generation_context=_chunks(delivered),
        tool_results=tuple(_tool_result(step) for step in delivered),
        answer=state.get("answer"),
        citations=state.get("citations", ()),
    )


def _chunks(steps: list[ToolStep]) -> tuple[Chunk, ...]:
    return tuple(chunk for step in steps for chunk in step.result.chunks)


def _tool_result(step: ToolStep) -> ToolResult:
    """O resultado como a geração o recebeu: o texto cercado, sempre não confiável (princípio VI)."""
    return ToolResult(
        content=step.result.text, untrusted=True, truncated=step.result.truncated, error=step.result.error
    )
