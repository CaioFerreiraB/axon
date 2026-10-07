"""Nós comuns aos flows: preparação, geração e validação.

Cada nó delega a um seam (002, 006) ou a uma função pura de `domain/` e escreve no canal de stream. É esta magreza que
torna o grafo reescrevível: a lógica vive nos serviços, o grafo só ordena (ADR-001, SC-001).
"""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from ai_core.graph.adapters.langgraph.state import AgentContext, AgentState
from ai_core.graph.adapters.langgraph.view import turn_view
from ai_core.graph.api import ExecutionIssue
from ai_core.graph.domain.budget import Trimmed, estimate_tokens, trim_results
from ai_core.graph.domain.transcript import generation_messages
from ai_core.observability.api import ValidationRun

STAGE_PREPARE = "prepare_context"
STAGE_GENERATE = "generate"
STAGE_VALIDATE = "validate_answer"

TOKEN = "token"
PROGRESS = "progress"


def _writer() -> Any:
    return get_stream_writer()


def _context() -> AgentContext:
    return get_runtime(AgentContext).context


async def prepare_context(state: AgentState) -> dict[str, Any]:
    """Preparação de contexto pack a pack (002). O motor carrega as fatias; não lê nem interpreta o que há nelas."""
    ctx = _context()
    _writer()({"kind": PROGRESS, "stage": STAGE_PREPARE})
    slices = await ctx.hooks.prepare(ctx.composition, turn_view(state), state.get("packs", {}))
    return {"packs": {name: dict(values) for name, values in slices.items()}}


async def generate(state: AgentState) -> dict[str, Any]:
    """Geração pelo papel `generation` (006), com os fragmentos de instrução dos packs (002) e, no `agentic`, a
    transcrição do loop (`domain/transcript.py`).

    O progresso sai **antes** da primeira chamada: é o primeiro sinal que a SC-004 mede, e ele chega mesmo quando o
    modelo demora a produzir o primeiro token. Com teto de contexto (só no `agentic`), os resultados mais antigos saem
    antes da chamada (`domain/budget.py`, R22) e a redução fica registrada.
    """
    ctx = _context()
    writer = _writer()
    writer({"kind": PROGRESS, "stage": STAGE_GENERATE})

    prompts = ctx.hooks.system_prompts(ctx.composition)
    full = generation_messages(prompts, state.get("messages", ()), state.get("steps", ()))
    ceiling = state.get("ceiling")
    trimmed = trim_results(full, ceiling)

    # Os validators que reescrevem em streaming filtram cada pedaço antes de ele sair (ADR-024): só o que o filtro
    # libera vira token, e a cauda sai no fim. Sem esses validators, o filtro deixa tudo passar.
    answer_filter = ctx.hooks.open_answer_stream(ctx.composition, turn_view(state), state.get("packs", {}))
    async for chunk in ctx.router.for_role("generation").stream(trimmed.messages):
        text = chunk["delta"]
        if text:
            released = answer_filter.feed(text)
            if released:
                writer({"kind": TOKEN, "text": released})
    streamed = answer_filter.finish()
    if streamed.tail:
        writer({"kind": TOKEN, "text": streamed.tail})
    return {
        "answer": streamed.answer,
        "streamed": streamed,
        "omitted": trimmed.omitted,
        "errors": _budget_issues(trimmed, ceiling),
    }


def _budget_issues(trimmed: Trimmed, ceiling: int | None) -> list[ExecutionIssue]:
    issues: list[ExecutionIssue] = []
    if trimmed.omitted:
        issues.append(
            ExecutionIssue(
                stage=STAGE_GENERATE,
                kind="ContextTrimmed",
                message=f"{trimmed.omitted} resultado(s) de tool omitido(s) para caber no teto de {ceiling} tokens",
                severity="notice",
            )
        )
    if trimmed.overflow:
        issues.append(
            ExecutionIssue(
                stage=STAGE_GENERATE,
                kind="ContextOverflow",
                message=(
                    f"contexto estimado em {estimate_tokens(trimmed.messages)} tokens, acima do teto de {ceiling}, "
                    "mesmo sem resultados de tool"
                ),
                severity="notice",
            )
        )
    return issues


async def validate_answer(state: AgentState) -> dict[str, Any]:
    """Validators dos packs, em sequência (002). Não chamam modelos e não decidem se a execução falhou."""
    ctx = _context()
    _writer()({"kind": PROGRESS, "stage": STAGE_VALIDATE})
    streamed = state.get("streamed")
    outcome = await ctx.hooks.validate(ctx.composition, turn_view(state), state.get("packs", {}), streamed=streamed)
    for run in outcome.runs:
        ctx.trace.emit(
            ValidationRun(
                request_id=state["request_id"],
                pack=run.pack,
                validator=run.validator,
                ok=run.result.ok,
                issues=tuple(run.result.issues),
                flags=run.result.flags,
            )
        )
    return {"validation": outcome, "errors": _deliver_rest(state.get("answer"), outcome.answer)}


def _deliver_rest(delivered: str | None, final: str | None) -> list[ExecutionIssue]:
    """O que os validators em lote só acrescentaram sai como token; reescrita no meio fica registrada (ADR-024)."""
    if final is None or delivered is None or final == delivered:
        return []
    if final.startswith(delivered):
        _writer()({"kind": TOKEN, "text": final[len(delivered) :]})
        return []
    return [
        ExecutionIssue(
            stage=STAGE_VALIDATE,
            kind="AnswerRewritten",
            message=(
                "um validator reescreveu a resposta depois da geração; com streaming, o cliente recebeu o texto "
                "anterior"
            ),
            severity="notice",
        )
    ]
