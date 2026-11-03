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

from axon_ai.capabilities.api import ToolCall, ToolContext, ToolSession
from axon_ai.graph.adapters.langgraph.nodes.common import ATTACHMENT, CHART, PROGRESS, finished
from axon_ai.graph.adapters.langgraph.state import AgentContext, AgentState
from axon_ai.graph.api import CatalogOutcome, ControllerOutcome, ExecutionIssue, ToolCallsOutcome
from axon_ai.graph.domain.actions import (
    AnswerAction,
    InvalidAction,
    ToolAction,
    ViewImageAction,
    parse_action,
    response_format,
)
from axon_ai.graph.domain.budget import estimate_tokens, exceeds
from axon_ai.graph.domain.limits import ITERATION_LIMIT, DecisionKind, after_decision
from axon_ai.graph.domain.steps import tool_summary
from axon_ai.graph.domain.transcript import (
    InvalidStep,
    Step,
    ToolStep,
    ViewStep,
    controller_messages,
    date_instruction,
    repeats,
    repeats_view,
)
from axon_ai.llm.api import ModelCallFailed
from axon_ai.observability.api import ControllerDecision, DecisionAction, ExecutionError
from axon_ai_contracts import RETRIEVAL_FILTERS_KEY, JSONValue

STAGE_LOAD: Final = "load_capabilities"
STAGE_CONTROLLER: Final = "controller"
STAGE_EXECUTE: Final = "execute_tool"


def _context() -> AgentContext:
    return get_runtime(AgentContext).context


def _progress(stage: str, detail: str | None = None) -> None:
    get_stream_writer()({"kind": PROGRESS, "stage": stage, "detail": detail})


def _decision(
    state: AgentState,
    iteration: int,
    action: DecisionAction,
    *,
    tool: str | None = None,
    reason: str | None = None,
    images: tuple[str, ...] | None = None,
) -> str:
    _context().trace.emit(
        ControllerDecision(
            request_id=state["request_id"],
            iteration=iteration,
            action=action,
            tool=tool,
            reason=reason,
            images=images,
        )
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
            mcp_delegation=ctx.mcp_delegation,
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
    """Abre a sessão (`open_session`); catálogo vazio vai direto à geração, sem chamar o controller (R27) — salvo se
    há imagem candidata: aí o controller decide se ela vai à geração (ADR-044, R51)."""
    _progress(STAGE_LOAD)
    session, issues = await open_session(state, stage=STAGE_LOAD)
    finished(STAGE_LOAD, CatalogOutcome(tools=len(session.tools), unavailable=tuple(session.unavailable)))
    decide = bool(session.tools) or bool(_context().images.candidates)
    return {"route": STAGE_CONTROLLER if decide else "generate", "errors": issues}


async def controller(state: AgentState) -> dict[str, Any]:
    """Uma iteração: confere o teto, pede a ação ao papel `controller` e decide a rota.

    Falha do modelo não encerra a execução nem é repetida: vai à geração com o que há (FR-006a, R21).
    """
    ctx = _context()
    session = ctx.tools.get()
    tools = list(session.tools.values())
    done = state.get("iteration", 0)
    iteration = done + 1
    today = date_instruction(state["reference_time"], ctx.timezone)
    images = tuple(item.id for item in ctx.images.candidates)
    messages = controller_messages(
        tools,
        state.get("messages", ()),
        state.get("steps", ()),
        today=today,
        images=images,
        send_own=ctx.images.to_controller,
    )

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
        response = await model.complete(messages, response_format=response_format(tools, images))
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

    action = parse_action(response["message"].get("content"), images)
    if isinstance(action, ViewImageAction):
        return {"iteration": iteration} | _view(state, iteration, ref, action.id)
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
        call = ToolCall(name=action.name, arguments=action.arguments)
        if repeats(call, state.get("steps", ())):
            # O resultado já está na transcrição: repetir só gastaria iteração. Vai à geração com o que há (R50).
            return {
                "iteration": iteration,
                "route": "generate",
                "decisions": [_decision(state, iteration, "tool", tool=action.name)],
                "errors": [
                    ExecutionIssue(
                        stage=STAGE_CONTROLLER,
                        kind="RepeatedAction",
                        message=(
                            f"iteração {iteration}: '{action.name}' pedida de novo com os mesmos argumentos; a "
                            "resposta foi gerada com o que havia"
                        ),
                        severity="notice",
                    )
                ],
            }
        return {
            "iteration": iteration,
            "route": STAGE_EXECUTE,
            "pending": call,
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
    # As imagens da tool vão ao usuário, uma vez por `id` na execução, depois do desfecho da etapa (ADR-044, item 4).
    seen = {item.id for item in state.get("attachments", ())}
    fresh = [item for item in result.attachments if item.id not in seen]
    writer = get_stream_writer()
    for item in fresh:
        writer({"kind": ATTACHMENT, "attachment": item, "tool": call.name})
    # Os gráficos também, do mesmo jeito (ADR-052, item 2).
    drawn = {item.id for item in state.get("charts", ())}
    charts = [item for item in {chart.id: chart for chart in result.charts}.values() if item.id not in drawn]
    for chart in charts:
        writer({"kind": CHART, "chart": chart, "tool": call.name})
    iteration = state.get("iteration", 0)
    return _after(state, "tool", iteration, step=ToolStep(iteration=iteration, call=call, result=result)) | {
        "pending": None,
        "attachments": fresh,
        "charts": charts,
    }


def _view(state: AgentState, iteration: int, model: str, image: str) -> dict[str, Any]:
    """`view_image`: marca a imagem para a geração e conta como iteração; a mesma imagem de novo segue a regra da ação
    repetida (R50) e vai à geração (ADR-044, item 8)."""
    finished(STAGE_CONTROLLER, ControllerOutcome(iteration=iteration, model=model, action="view_image", image=image))
    decision = _decision(state, iteration, "view_image", images=(image,))
    if repeats_view(image, state.get("steps", ())):
        return {
            "route": "generate",
            "decisions": [decision],
            "errors": [
                ExecutionIssue(
                    stage=STAGE_CONTROLLER,
                    kind="RepeatedAction",
                    message=(
                        f"iteração {iteration}: a imagem {image} pedida de novo; a resposta foi gerada com o que havia"
                    ),
                    severity="notice",
                )
            ],
        }
    return _after(
        state, "view_image", iteration, step=ViewStep(iteration=iteration, image=image), decision=decision
    ) | {"viewed": [image]}


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
                kind=ITERATION_LIMIT,
                message=f"limite de {limit} iterações atingido; a resposta foi gerada com o que havia",
                severity="notice",
            )
        )
    return {"route": route.next, "steps": [step], "decisions": decisions, "errors": errors}
