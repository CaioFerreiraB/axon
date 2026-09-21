"""Topologias do core, escritas à mão (ADR-001), e o registro que as nomeia.

Um flow novo é decisão arquitetural registrada em ADR (FR-003); packs não criam, alteram nem inspecionam flows
(FR-004) — eles apenas selecionam um nome.
"""

from __future__ import annotations

from collections.abc import Mapping

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_core.graph.adapters.langgraph.nodes import STAGE_GENERATE, STAGE_PREPARE, STAGE_VALIDATE, generate
from ai_core.graph.adapters.langgraph.nodes import prepare_context as prepare_context_node
from ai_core.graph.adapters.langgraph.nodes import validate_answer as validate_answer_node
from ai_core.graph.adapters.langgraph.state import AgentContext, AgentState
from ai_core.graph.api import FLOW_CHAT

type FlowGraph = CompiledStateGraph[AgentState, AgentContext, AgentState, AgentState]
"""Grafo compilado deste módulo. O alias existe para não espalhar os parâmetros do framework pelo código."""


def chat_graph() -> FlowGraph:
    """`chat`: sem tools e sem RAG. Topologia da Fase 1 e fallback quando nenhuma capacidade é necessária."""
    builder = StateGraph(AgentState, context_schema=AgentContext)
    builder.add_node(STAGE_PREPARE, prepare_context_node)
    builder.add_node(STAGE_GENERATE, generate)
    builder.add_node(STAGE_VALIDATE, validate_answer_node)
    builder.add_edge(START, STAGE_PREPARE)
    builder.add_edge(STAGE_PREPARE, STAGE_GENERATE)
    builder.add_edge(STAGE_GENERATE, STAGE_VALIDATE)
    builder.add_edge(STAGE_VALIDATE, END)
    return builder.compile()


def compiled_flows() -> Mapping[str, FlowGraph]:
    """Registro nome → grafo compilado. Compilar acontece uma vez, no boot; a execução só passa o contexto."""
    return {FLOW_CHAT: chat_graph()}
