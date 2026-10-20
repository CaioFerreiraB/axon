"""Nós do `rag_first`: recuperar, reordenar e o portão de cobertura (US3; research R37 a R42, R45).

Finos como os outros: a recuperação é a sessão de tools da 004 (ADR-005), o rerank é o Pack Hooks da 002, e toda
decisão — trechos aceitos, junção, cobertura, rota, corte pelo teto — é função pura de `domain/` (`gate.py`,
`budget.py`). O portão só escreve a rota; as arestas a leem.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Final

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from axon_ai.capabilities.api import ToolCall
from axon_ai.graph.adapters.langgraph.nodes.agentic import STAGE_CONTROLLER, open_session
from axon_ai.graph.adapters.langgraph.nodes.common import PROGRESS, STAGE_GENERATE, finished
from axon_ai.graph.adapters.langgraph.state import AgentContext, AgentState
from axon_ai.graph.api import (
    ExecutionIssue,
    GateOutcome,
    RagSettings,
    RerankOutcome,
    ToolCallsOutcome,
    ToolCallSummary,
)
from axon_ai.graph.domain.budget import fit_chunks
from axon_ai.graph.domain.gate import (
    Passage,
    RerankRefused,
    accept_reranked,
    best_score,
    by_tool,
    first,
    gate_route,
    group_by_pack,
    is_covered,
    merge,
    pack_of,
    retrieval_tools,
)
from axon_ai.graph.domain.steps import source_refs, tool_summary
from axon_ai.graph.domain.transcript import ToolStep, generation_messages
from axon_ai.observability.api import CoverageGate, ExecutionError

STAGE_RETRIEVE: Final = "retrieve"
STAGE_RERANK: Final = "rerank"
STAGE_GATE: Final = "gate"
ROUTE_END: Final = "end"


def _context() -> AgentContext:
    return get_runtime(AgentContext).context


def _progress(stage: str, detail: str) -> None:
    get_stream_writer()({"kind": PROGRESS, "stage": stage, "detail": detail})


def _settings(ctx: AgentContext) -> RagSettings:
    if ctx.rag is None:
        raise RuntimeError("flow rag_first sem RagSettings")
    return ctx.rag


async def retrieve(state: AgentState) -> dict[str, Any]:
    """Abre a sessão e executa cada tool de recuperação do catálogo com a pergunta e `top_k = candidates` (R37).

    O gateway emite o `ToolCall` e repassa os filtros do pack sem leitura (US3 cen. 4). Status diferente de `ok`
    encerra a execução **sem gerar**: o Assistant depende do índice, e "sem resultado" esconderia a falha
    (princípio VII).
    """
    ctx = _context()
    settings = _settings(ctx)
    session, issues = await open_session(state, stage=STAGE_RETRIEVE)
    tools = retrieval_tools(session.tools.values())
    _progress(STAGE_RETRIEVE, f"{len(tools)} tool(s) de recuperação")
    found: list[Passage] = []
    calls: list[ToolCallSummary] = []
    for tool in tools:
        call = ToolCall(name=tool.name, arguments={"query": state["question"], "top_k": settings.candidates})
        result = await session.execute(call)
        calls.append(tool_summary(call, result))
        if result.status != "ok":
            finished(STAGE_RETRIEVE, ToolCallsOutcome(calls=tuple(calls)))
            reason = result.error or result.status
            message = f"tool '{tool.name}': {reason}"
            ctx.trace.emit(
                ExecutionError(
                    request_id=state["request_id"], stage=STAGE_RETRIEVE, kind="RetrievalFailed", message=message
                )
            )
            failure = ExecutionIssue(stage=STAGE_RETRIEVE, kind="RetrievalFailed", message=message)
            return {"route": ROUTE_END, "errors": [*issues, failure]}
        found.extend(Passage(pack=pack_of(tool.name), tool=tool.name, chunk=chunk) for chunk in result.chunks)
    finished(STAGE_RETRIEVE, ToolCallsOutcome(calls=tuple(calls)))
    return {"route": STAGE_RERANK, "retrieved": tuple(found), "errors": issues}


async def rerank(state: AgentState) -> dict[str, Any]:
    """Cada pack com o reranker dele, `top_k = passages`; sem reranker, os primeiros. Junção por score (R38).

    Reranker que levanta ou foge do contrato (trecho estranho, repetido, além de `top_k`) degrada para a ordem do
    retriever, com registro — nunca em silêncio.
    """
    ctx = _context()
    settings = _settings(ctx)
    candidates = state.get("retrieved", ())
    _progress(STAGE_RERANK, f"{len(candidates)} candidato(s)")
    groups: list[tuple[Passage, ...]] = []
    issues: list[ExecutionIssue] = []
    degraded: list[str] = []
    for pack, documents in group_by_pack(candidates).items():
        reranker = ctx.hooks.reranker(ctx.composition, pack)
        if reranker is None:
            groups.append(first(documents, settings.passages))
            continue
        try:
            reordered = await reranker.rerank(
                state["question"], [item.chunk for item in documents], top_k=settings.passages
            )
            accepted = accept_reranked(documents, list(reordered), top_k=settings.passages)
        # Amplo de propósito: o reranker é código de pack, e a falha dele é degradação, não fim da execução (R38).
        except Exception as error:
            accepted = RerankRefused(reason=f"levantou {type(error).__name__}: {error}")
        if isinstance(accepted, RerankRefused):
            degraded.append(pack)
            issues.append(
                ExecutionIssue(
                    stage=STAGE_RERANK,
                    kind="RerankFailed",
                    message=f"reranker do pack '{pack}' {accepted.reason}; valeu a ordem do retriever",
                    severity="notice",
                )
            )
            accepted = first(documents, settings.passages)
        groups.append(accepted)
    reranked = merge(groups, settings.passages)
    finished(
        STAGE_RERANK,
        RerankOutcome(
            candidates=len(candidates),
            kept=source_refs(item.chunk for item in reranked),
            degraded=tuple(degraded),
        ),
    )
    return {"reranked": reranked, "errors": issues}


async def gate(state: AgentState) -> dict[str, Any]:
    """O portão de cobertura (R39, R40) e, no caminho coberto, os trechos que cabem no teto como passos de tool (R41,
    R42). Uma única decisão, registrada no trace como `CoverageGate`."""
    ctx = _context()
    settings = _settings(ctx)
    reranked = state.get("reranked", ())
    _progress(STAGE_GATE, f"{len(reranked)} trecho(s)")
    session = ctx.tools.get()
    covered = is_covered(reranked, settings.min_score)
    route = gate_route(covered, escalate=ctx.escalate and bool(session.tools))
    decision = GateOutcome(covered=covered, route=route, best_score=best_score(reranked), threshold=settings.min_score)
    ctx.trace.emit(
        CoverageGate(
            request_id=state["request_id"],
            candidates=len(state.get("retrieved", ())),
            passages=len(reranked),
            best_score=decision.best_score,
            threshold=settings.min_score,
            covered=covered,
            route=route,
        )
    )
    if route == "controller":
        finished(STAGE_GATE, decision)
        return {"route": STAGE_CONTROLLER}
    if route == "fallback":
        finished(STAGE_GATE, decision)
        return {
            "route": STAGE_GENERATE,
            "errors": [
                ExecutionIssue(
                    stage=STAGE_GATE,
                    kind="CoverageInsufficient",
                    message=_insufficient(len(reranked), settings.min_score, controller=ctx.escalate),
                    severity="notice",
                )
            ],
        }

    prompts = ctx.hooks.system_prompts(ctx.composition)

    def steps_for(kept: tuple[Passage, ...] | list[Passage]) -> list[ToolStep]:
        return [
            ToolStep(
                iteration=index,
                call=ToolCall(name=name, arguments={"query": state["question"]}),
                result=session.fence_chunks(name, chunks),
                synthetic=True,
            )
            for index, (name, chunks) in enumerate(by_tool(kept).items(), start=1)
        ]

    fitted = fit_chunks(
        reranked,
        lambda kept: generation_messages(prompts, state.get("messages", ()), steps_for(list(kept))),
        state.get("ceiling"),
    )
    issues: list[ExecutionIssue] = []
    if fitted.dropped:
        issues.append(
            ExecutionIssue(
                stage=STAGE_GATE,
                kind="ContextTrimmed",
                message=(
                    f"{fitted.dropped} trecho(s) de menor posição tirado(s) para caber no teto de "
                    f"{state.get('ceiling')} tokens"
                ),
                severity="notice",
            )
        )
    finished(STAGE_GATE, replace(decision, delivered=len(fitted.items)))
    return {"route": STAGE_GENERATE, "steps": steps_for(fitted.items), "errors": issues}


def _insufficient(passages: int, min_score: float | None, *, controller: bool) -> str:
    found = "nenhum trecho recuperado" if passages == 0 else f"melhor score abaixo do limiar {min_score}"
    why = "não há tool para o loop" if controller else "o Assistant não tem controller"
    return f"{found}; a resposta foi gerada sem trechos ({why})"
