"""Topologias do core, escritas à mão (ADR-001), e o registro que as nomeia.

Um flow novo é decisão arquitetural registrada em ADR (FR-003); packs não criam, alteram nem inspecionam flows
(FR-004) — eles apenas selecionam um nome.
"""

from __future__ import annotations

from collections.abc import Mapping

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_core.graph.adapters.langgraph.nodes.agentic import (
    STAGE_CONTROLLER,
    STAGE_EXECUTE,
    STAGE_LOAD,
    controller,
    execute_tool,
    load_capabilities,
)
from ai_core.graph.adapters.langgraph.nodes.common import STAGE_GENERATE, STAGE_PREPARE, STAGE_VALIDATE, generate
from ai_core.graph.adapters.langgraph.nodes.common import prepare_context as prepare_context_node
from ai_core.graph.adapters.langgraph.nodes.common import validate_answer as validate_answer_node
from ai_core.graph.adapters.langgraph.state import AgentContext, AgentState
from ai_core.graph.api import FLOW_AGENTIC, FLOW_CHAT

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


def _route(state: AgentState) -> str:
    """As arestas só leem a rota que o passo calculou por `domain/limits.py` — nenhuma decide por conta própria."""
    return state["route"]


def agentic_graph() -> FlowGraph:
    """`agentic`: loop do controller sobre o catálogo da execução (US2, design.md "agentic — loop de controller").

    A aresta para a geração no limite não é opcional: é ela que torna o loop finito (FR-006, SC-002).
    """
    builder = StateGraph(AgentState, context_schema=AgentContext)
    builder.add_node(STAGE_PREPARE, prepare_context_node)
    builder.add_node(STAGE_LOAD, load_capabilities)
    builder.add_node(STAGE_CONTROLLER, controller)
    builder.add_node(STAGE_EXECUTE, execute_tool)
    builder.add_node(STAGE_GENERATE, generate)
    builder.add_node(STAGE_VALIDATE, validate_answer_node)
    builder.add_edge(START, STAGE_PREPARE)
    builder.add_edge(STAGE_PREPARE, STAGE_LOAD)
    builder.add_conditional_edges(STAGE_LOAD, _route, [STAGE_CONTROLLER, STAGE_GENERATE])
    builder.add_conditional_edges(STAGE_CONTROLLER, _route, [STAGE_EXECUTE, STAGE_CONTROLLER, STAGE_GENERATE])
    builder.add_conditional_edges(STAGE_EXECUTE, _route, [STAGE_CONTROLLER, STAGE_GENERATE])
    builder.add_edge(STAGE_GENERATE, STAGE_VALIDATE)
    builder.add_edge(STAGE_VALIDATE, END)
    return builder.compile()


def compiled_flows() -> Mapping[str, FlowGraph]:
    """Registro nome → grafo compilado. Compilar acontece uma vez, no boot; a execução só passa o contexto."""
    return {FLOW_CHAT: chat_graph(), FLOW_AGENTIC: agentic_graph()}
