"""Projeção do estado interno na Turn View do contrato 001 (ADR-011).

Manter a projeção num arquivo só é o que permite reescrever o estado sem tocar em pack nenhum. As fatias por pack
(`own_slice`, `dependency_slices`) são recortadas pela 002 a partir do mapa de fatias — este módulo entrega a visão
global e o mapa.
"""

from __future__ import annotations

from ai_core.graph.adapters.langgraph.state import AgentState
from ai_core_contracts import TurnView


def turn_view(state: AgentState) -> TurnView:
    """Visão somente-leitura da execução, como os hooks de pack a enxergam.

    No `chat` não há retrieval nem tools, então `retrieved`, `reranked`, `generation_context` e `tool_results` ficam
    vazios — `generation_context` é o campo que os validators leem para verificar citação (ADR-007), e vazio é a
    resposta correta para um flow que não entrega chunk nenhum à geração.
    """
    return TurnView(
        request_id=state["request_id"],
        assistant=state["assistant"],
        reference_time=state["reference_time"],
        question=state["question"],
        messages=state.get("messages", ()),
        answer=state.get("answer"),
        citations=state.get("citations", ()),
    )
