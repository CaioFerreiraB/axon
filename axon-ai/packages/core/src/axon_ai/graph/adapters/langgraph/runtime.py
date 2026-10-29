"""Tradução do streaming do framework nos eventos do seam (research R2).

O canal `custom` entrega o que os nós escrevem **enquanto** rodam — é o que sustenta o streaming (princípio XI) e a
SC-004; o último `values` traz o estado completo, de onde sai o `FinalEvent`. Depois do primeiro evento nada levanta:
exceção vira `FinalEvent` com erro nomeado, preservando a resposta parcial (research R6).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any, Final, Literal, cast

from axon_ai.capabilities.api import CatalogConflict
from axon_ai.graph.adapters.langgraph.flows import FlowGraph, compiled_flows
from axon_ai.graph.adapters.langgraph.nodes.agentic import STAGE_LOAD
from axon_ai.graph.adapters.langgraph.nodes.common import ATTACHMENT, CHART, PROGRESS, STEP, TOKEN
from axon_ai.graph.adapters.langgraph.state import AgentContext, AgentState
from axon_ai.graph.api import (
    AttachmentEvent,
    ChartEvent,
    ExecutionEvent,
    ExecutionIssue,
    FinalEvent,
    ProgressEvent,
    StepFinished,
    TokenEvent,
)
from axon_ai.graph.domain.images import unique, unique_charts
from axon_ai.graph.domain.outcome import final_event
from axon_ai.graph.ports import ExecutionPlan
from axon_ai.llm.api import ModelCallFailed
from axon_ai.observability.api import ExecutionError as TraceExecutionError
from axon_ai.packs.api import PackHookError

STREAM_MODES: Final[list[Literal["custom", "values"]]] = ["custom", "values"]
UNKNOWN_STAGE: Final = "execution"


class LangGraphRuntime:
    """Adapter da porta `FlowRuntime`. É o único objeto do módulo que conhece o framework de grafo."""

    def __init__(self, flows: Mapping[str, FlowGraph] | None = None) -> None:
        self._flows = dict(flows) if flows is not None else dict(compiled_flows())

    def names(self) -> frozenset[str]:
        return frozenset(self._flows)

    async def events(self, plan: ExecutionPlan) -> AsyncIterator[ExecutionEvent]:
        """Executa o grafo do plano e traduz o que ele produz."""
        graph = self._flows[plan.flow]
        state: AgentState = {
            "request_id": plan.request_id,
            "assistant": plan.assistant,
            "flow": plan.flow,
            "reference_time": plan.reference_time,
            "question": plan.question,
            "messages": tuple(plan.messages),
            "packs": {},
            "errors": [],
            "steps": [],
            "decisions": [],
            "iteration": 0,
            "limit": plan.max_iterations,
            "ceiling": plan.max_context_tokens,
            "pending": None,
            "omitted": 0,
            "retrieved": (),
            "reranked": (),
            "gate_images": plan.images.gate,
            "viewed": list(plan.images.viewed),
            "attachments": [],
            "charts": [],
        }
        context = AgentContext(
            composition=plan.composition,
            hooks=plan.hooks,
            router=plan.router,
            trace=plan.trace,
            grant=plan.grant,
            capabilities=plan.capabilities,
            rag=plan.rag,
            escalate=plan.escalate,
            timezone=plan.timezone,
            images=plan.images,
        )

        generated = ""
        last: AgentState | None = None
        try:
            async for mode, chunk in graph.astream(state, context=context, stream_mode=STREAM_MODES):
                if mode == "custom":
                    event = _from_custom(chunk)
                    if isinstance(event, TokenEvent):
                        generated += event.text
                    yield event
                else:
                    # O framework tipa o pedaço de forma genérica; o schema do grafo garante que é o nosso estado.
                    last = cast(AgentState, chunk)
        # Amplo de propósito: o seam promete que nada levanta depois do primeiro evento (research R6).
        except Exception as error:
            issue = _issue(error)
            plan.trace.emit(
                TraceExecutionError(
                    request_id=plan.request_id,
                    stage=issue.stage,
                    kind=issue.kind,
                    message=issue.message,
                )
            )
            accumulated = tuple(last.get("errors", ())) if last is not None else ()
            images = unique(tuple(last.get("attachments", ()))) if last is not None else ()
            charts = unique_charts(tuple(last.get("charts", ()))) if last is not None else ()
            yield FinalEvent(answer=generated, errors=(*accumulated, issue), attachments=images, charts=charts)
            return

        yield _final(last, generated)


def _from_custom(chunk: Any) -> ExecutionEvent:
    if chunk.get("kind") == TOKEN:
        return TokenEvent(text=chunk["text"])
    if chunk.get("kind") == PROGRESS:
        return ProgressEvent(stage=chunk["stage"], detail=chunk.get("detail"))
    if chunk.get("kind") == STEP:
        return StepFinished(stage=chunk["stage"], outcome=chunk.get("outcome"))
    if chunk.get("kind") == ATTACHMENT:
        return AttachmentEvent(attachment=chunk["attachment"], tool=chunk["tool"])
    if chunk.get("kind") == CHART:
        return ChartEvent(chart=chunk["chart"], tool=chunk["tool"])
    raise ValueError(f"pedaço de stream desconhecido: {chunk!r}")


def _final(last: AgentState | None, generated: str) -> FinalEvent:
    if last is None:
        return FinalEvent(answer=generated)
    return final_event(
        generated=last.get("answer", generated),
        outcome=last.get("validation"),
        errors=tuple(last.get("errors", ())),
        attachments=tuple(last.get("attachments", ())),
        charts=tuple(last.get("charts", ())),
    )


def _issue(error: Exception) -> ExecutionIssue:
    """Erro de outro módulo vira erro nomeado: o pack que falhou, o provider e o modelo que não responderam, ou o nome
    em conflito no catálogo de tools (004)."""
    if isinstance(error, CatalogConflict):
        return ExecutionIssue(stage=STAGE_LOAD, kind=type(error).__name__, message=str(error))
    if isinstance(error, PackHookError):
        return ExecutionIssue(stage=error.hook, kind=type(error).__name__, message=f"pack '{error.pack}': {error}")
    if isinstance(error, ModelCallFailed):
        return ExecutionIssue(stage="generate", kind=type(error).__name__, message=str(error))
    return ExecutionIssue(stage=UNKNOWN_STAGE, kind=type(error).__name__, message=str(error))
