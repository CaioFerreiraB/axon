"""Adapter de fluxo em LangGraph: o único lugar do core que conhece o framework de grafo (ADR-011).

Reescrever o motor é trocar este pacote inteiro por outro que cumpra a porta `FlowRuntime` — `api.py`, `domain/` e
suas suítes permanecem (SC-001). A composition root (011) importa daqui apenas `langgraph_runtime()`.
"""

from __future__ import annotations

from axon_ai.graph.adapters.langgraph.runtime import LangGraphRuntime

__all__ = ["LangGraphRuntime", "langgraph_runtime"]


def langgraph_runtime() -> LangGraphRuntime:
    """Runtime com os flows do core compilados — uma vez, no boot."""
    return LangGraphRuntime()
