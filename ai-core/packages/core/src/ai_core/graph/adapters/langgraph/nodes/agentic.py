"""Nós do loop `agentic`: abrir a sessão de tools, decidir (controller) e executar.

Finos como os outros: cada um delega a um seam — a sessão da 004, o papel `controller` da 006, o Trace Sink da 009 — ou
a uma função pura de `domain/` (ação, limite, teto, transcrição). A rota de cada passo é calculada por
`domain/limits.py` e só lida pelas arestas (research R20).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from ai_core.capabilities.api import ToolCall, ToolContext, ToolSession
from ai_core.graph.adapters.langgraph.nodes.common import PROGRESS, finished
from ai_core.graph.adapters.langgraph.state import AgentContext, AgentState
from ai_core.graph.api import CatalogOutcome, ControllerOutcome, ExecutionIssue, ToolCallsOutcome
from ai_core.graph.domain.actions import AnswerAction, InvalidAction, ToolAction, parse_action, response_format
from ai_core.graph.domain.budget import estimate_tokens, exceeds
from ai_core.graph.domain.limits import DecisionKind, after_decision
from ai_core.graph.domain.steps import tool_summary
from ai_core.graph.domain.transcript import InvalidStep, Step, ToolStep, controller_messages
from ai_core.llm.api import ModelCallFailed
from ai_core.observability.api import ControllerDecision, DecisionAction, ExecutionError
from ai_core_contracts import RETRIEVAL_FILTERS_KEY, JSONValue

STAGE_LOAD: Final = "load_capabilities"
STAGE_CONTROLLER: Final = "controller"
STAGE_EXECUTE: Final = "execute_tool"


def _context() -> AgentContext:
    return get_runtime(AgentContext).context


def _progress(stage: str, detail: str | None = None) -> None:
    get_stream_writer()({"kind": PROGRESS, "stage": stage, "detail": detail})


def _decision(
    state: AgentState, iteration: int, action: DecisionAction, *, tool: str | None = None, reason: str | None = None
) -> str:
    _context().trace.emit(
        ControllerDecision(request_id=state["request_id"], iteration=iteration, action=action, tool=tool, reason=reason)
    )
    return action


def _retrieval_filters(slices: Mapping[str, Mapping[str, JSONValue]]) -> dict[str, Mapping[str, JSONValue]]:
    """Por pack, os filtros que ele publicou na própria fatia — repassados sem leitura (FR-008)."""
    filters: dict[str, Mapping[str, JSONValue]] = {}
    for pack, values in slices.items():
        published = values.get(RETRIEVAL_FILTERS_KEY)
        if isinstance(published, Mapping):
            filters[pack] = published
    return filters


async def open_session(state: AgentState, *, stage: str) -> tuple[ToolSession, list[ExecutionIssue]]:
    """Abre a sessão de tools da execução (004) depois da preparação, com os filtros das fatias, e a guarda no
    compartimento (R16). Usada pelo `load_capabilities` e pelo `retrieve` do `rag_first` (R37).

    MCP que falhou na descoberta fica fora do catálogo e vira registro `error` — degradação explícita, nunca silenciosa
    (princípio VII, R23).
    """
    ctx = _context()
    if ctx.capabilities is None or ctx.grant is None:
        raise RuntimeError(f"flow {state['flow']} sem gateway de tools")
    session = await ctx.capabilities.open(
        ctx.grant,
        ToolContext(
            request_id=state["request_id"],
            reference_time=state["reference_time"],
            retrieval_filters=_retrieval_filters(state.get("packs", {})),
        ),
    )
    ctx.tools.session = session
    issues = [
        ExecutionIssue(stage=stage, kind="McpUnavailable", message=f"MCP '{alias}': {reason}")
        for alias, reason in session.unavailable.items()
    ]
    return session, issues


async def load_capabilities(state: AgentState) -> dict[str, Any]:
    """Abre a sessão (`open_session`); catálogo vazio vai direto à geração, sem chamar o controller (R27)."""
    _progress(STAGE_LOAD)
    session, issues = await open_session(state, stage=STAGE_LOAD)
    finished(STAGE_LOAD, CatalogOutcome(tools=len(session.tools), unavailable=tuple(session.unavailable)))
    return {"route": STAGE_CONTROLLER if session.tools else "generate", "errors": issues}


async def controller(state: AgentState) -> dict[str, Any]:
    """Uma iteração: confere o teto, pede a ação ao papel `controller` e decide a rota.

    Falha do modelo não encerra a execução nem é repetida: vai à geração com o que há (FR-006a, R21).
    """
    ctx = _context()
    session = ctx.tools.get()
    tools = list(session.tools.values())
    done = state.get("iteration", 0)
    iteration = done + 1
    messages = controller_messages(tools, state.get("messages", ()), state.get("steps", ()))

    ceiling = state.get("ceiling")
    if exceeds(messages, ceiling):
        return {
            "route": "generate",
            "decisions": [_decision(state, done, "limit", reason="context")],
            "errors": [
                ExecutionIssue(
                    stage=STAGE_CONTROLLER,
                    kind="ContextLimit",
                    message=(
                        f"a iteração {iteration} levaria o contexto a {estimate_tokens(messages)} tokens, acima do "
                        f"teto de {ceiling}; a resposta foi gerada com o que havia"
                    ),
                    severity="notice",
                )
            ],
        }

    _progress(STAGE_CONTROLLER, f"iteração {iteration}")
    model = ctx.router.for_role("controller")
    ref = str(model.ref)
    try:
        response = await model.complete(messages, response_format=response_format(tools))
    except ModelCallFailed as error:
        finished(
            STAGE_CONTROLLER,
            ControllerOutcome(iteration=iteration, model=ref, action="failed", reason=type(error).__name__),
        )
        ctx.trace.emit(
            ExecutionError(
                request_id=state["request_id"], stage=STAGE_CONTROLLER, kind=type(error).__name__, message=str(error)
            )
        )
        issue = ExecutionIssue(stage=STAGE_CONTROLLER, kind=type(error).__name__, message=str(error))
        return {"iteration": iteration, "route": "generate", "errors": [issue]}

    action = parse_action(response["message"].get("content"))
    if isinstance(action, AnswerAction):
        finished(STAGE_CONTROLLER, ControllerOutcome(iteration=iteration, model=ref, action="answer"))
        return {"iteration": iteration, "route": "generate", "decisions": [_decision(state, iteration, "answer")]}
    if isinstance(action, ToolAction):
        finished(
            STAGE_CONTROLLER,
            ControllerOutcome(
                iteration=iteration, model=ref, action="tool", tool=action.name, arguments=action.arguments
            ),
        )
        return {
            "iteration": iteration,
            "route": STAGE_EXECUTE,
            "pending": ToolCall(name=action.name, arguments=action.arguments),
            "decisions": [_decision(state, iteration, "tool", tool=action.name)],
        }
    # A iteração conta mesmo inválida (US2 cen. 3): sem isso, um controller que só erra rodaria sem fim (SC-002).
    finished(
        STAGE_CONTROLLER, ControllerOutcome(iteration=iteration, model=ref, action="invalid", reason=action.reason)
    )
    return {"iteration": iteration} | _after(
        state,
        "invalid",
        iteration,
        step=InvalidStep(iteration=iteration, reason=action.reason),
        decision=_decision(state, iteration, "invalid", reason=action.reason),
        issue=_invalid(iteration, action),
    )


async def execute_tool(state: AgentState) -> dict[str, Any]:
    """Executa o pedido pelo gateway (004) e acumula o resultado cercado; a rota vem do limite."""
    ctx = _context()
    call = state.get("pending")
    if call is None:
        raise RuntimeError("execute_tool sem pedido do controller")
    _progress(STAGE_EXECUTE, call.name)
    result = await ctx.tools.get().execute(call)
    finished(STAGE_EXECUTE, ToolCallsOutcome(calls=(tool_summary(call, result),)))
    iteration = state.get("iteration", 0)
    return _after(state, "tool", iteration, step=ToolStep(iteration=iteration, call=call, result=result)) | {
        "pending": None
    }


def _invalid(iteration: int, action: InvalidAction) -> ExecutionIssue:
    return ExecutionIssue(
        stage=STAGE_CONTROLLER,
        kind="InvalidAction",
        message=f"iteração {iteration}: {action.reason}",
        severity="notice",
    )


def _after(
    state: AgentState,
    kind: DecisionKind,
    iteration: int,
    *,
    step: Step,
    decision: str | None = None,
    issue: ExecutionIssue | None = None,
) -> dict[str, Any]:
    """Acumula o passo e aplica a tabela de rotas; no limite, registra o truncamento (FR-006)."""
    limit = state.get("limit")
    if limit is None:
        raise RuntimeError("flow agentic sem limite de iterações")
    route = after_decision(kind, iteration, limit)
    decisions = [] if decision is None else [decision]
    errors = [] if issue is None else [issue]
    if route.truncated:
        decisions.append(_decision(state, iteration, "limit", reason="iterations"))
        errors.append(
            ExecutionIssue(
                stage=STAGE_CONTROLLER,
                kind="IterationLimit",
                message=f"limite de {limit} iterações atingido; a resposta foi gerada com o que havia",
                severity="notice",
            )
        )
    return {"route": route.next, "steps": [step], "decisions": decisions, "errors": errors}
