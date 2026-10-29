"""Nós comuns aos flows: preparação, geração e validação.

Cada nó delega a um seam (002, 006) ou a uma função pura de `domain/` e escreve no canal de stream. É esta magreza que
torna o grafo reescrevível: a lógica vive nos serviços, o grafo só ordena (ADR-001, SC-001).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from axon_ai.graph.adapters.langgraph.state import AgentContext, AgentState
from axon_ai.graph.adapters.langgraph.view import turn_view
from axon_ai.graph.api import FLOW_AGENTIC, ExecutionIssue, GenerationOutcome, StepOutcome
from axon_ai.graph.domain.budget import Trimmed, estimate_tokens, trim_results
from axon_ai.graph.domain.images import chosen
from axon_ai.graph.domain.markup import ToolMarkupFilter
from axon_ai.graph.domain.outcome import EMPTY_ANSWER
from axon_ai.graph.domain.transcript import date_instruction, generation_messages
from axon_ai.observability.api import Retrieval, RetrievedChunk, ValidationRun
from axon_ai_contracts import ChatUsage, Chunk

STAGE_PREPARE = "prepare_context"
STAGE_GENERATE = "generate"
STAGE_VALIDATE = "validate_answer"

TOKEN = "token"
PROGRESS = "progress"
STEP = "step"
ATTACHMENT = "attachment"
CHART = "chart"


def _writer() -> Any:
    return get_stream_writer()


def finished(stage: str, outcome: StepOutcome | None = None) -> None:
    """A etapa terminou, com o desfecho dela (ADR-028). Sai depois de todo o trabalho e de todo token da etapa."""
    _writer()({"kind": STEP, "stage": stage, "outcome": outcome})


def _context() -> AgentContext:
    return get_runtime(AgentContext).context


async def prepare_context(state: AgentState) -> dict[str, Any]:
    """Preparação de contexto pack a pack (002). O motor carrega as fatias; não lê nem interpreta o que há nelas."""
    ctx = _context()
    _writer()({"kind": PROGRESS, "stage": STAGE_PREPARE})
    slices = await ctx.hooks.prepare(ctx.composition, turn_view(state), state.get("packs", {}))
    finished(STAGE_PREPARE)
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
    # A data vai onde o loop correu: no `agentic` e no `rag_first` que escalou (R50). O `chat` segue como na Fase 1.
    looped = state["flow"] == FLOW_AGENTIC or state.get("iteration", 0) > 0
    today = date_instruction(state["reference_time"], ctx.timezone) if looped else None
    full = generation_messages(
        prompts,
        state.get("messages", ()),
        state.get("steps", ()),
        today=today,
        tools=looped,
        **generation_images(state),
    )
    ceiling = state.get("ceiling")
    trimmed = trim_results(full, ceiling)

    # Os validators que reescrevem em streaming filtram cada pedaço antes de ele sair (ADR-024): só o que o filtro
    # libera vira token, e a cauda sai no fim. Sem esses validators, o filtro deixa tudo passar.
    answer_filter = ctx.hooks.open_answer_stream(ctx.composition, turn_view(state), state.get("packs", {}))
    # Antes deles, sai a marcação de chamada de tool que o modelo escreva como texto (`domain/markup.py`).
    markup = ToolMarkupFilter()
    model = ctx.router.for_role("generation")
    usage: ChatUsage | None = None

    def release(text: str) -> None:
        released = answer_filter.feed(text) if text else ""
        if released:
            writer({"kind": TOKEN, "text": released})

    async for chunk in model.stream(trimmed.messages):
        usage = chunk.get("usage", usage)
        release(markup.feed(chunk["delta"]))
    release(markup.finish())
    streamed = answer_filter.finish()
    if streamed.tail:
        writer({"kind": TOKEN, "text": streamed.tail})
    issues = _budget_issues(trimmed, ceiling)
    if markup.removed:
        issues.append(
            ExecutionIssue(
                stage=STAGE_GENERATE,
                kind="ToolMarkupRemoved",
                message=f"{markup.removed} chamada(s) de tool escrita(s) como texto pelo modelo, fora da resposta",
                severity="notice",
            )
        )
    finished(
        STAGE_GENERATE,
        GenerationOutcome(
            model=str(model.ref),
            input_tokens=None if usage is None else usage["prompt_tokens"],
            output_tokens=None if usage is None else usage["completion_tokens"],
        ),
    )
    return {
        "answer": streamed.answer,
        "streamed": streamed,
        "omitted": trimmed.omitted,
        "errors": issues,
    }


def generation_images(state: AgentState) -> dict[str, Any]:
    """As imagens da geração (ADR-044): as do usuário, se o papel as recebe, e as candidatas escolhidas."""
    images = _context().images
    return {"send_own": images.to_generation, "shown": chosen(images.candidates, state.get("viewed", ()))}


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
    view = turn_view(state)
    _emit_retrieval(state["request_id"], view.retrieved, view.reranked, view.generation_context)
    streamed = state.get("streamed")
    outcome = await ctx.hooks.validate(ctx.composition, view, state.get("packs", {}), streamed=streamed)
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
    errors = _deliver_rest(state.get("answer"), outcome.answer)
    final = outcome.answer if outcome.answer is not None else state.get("answer")
    if not (final or "").strip():
        # Depois dos validators, que precisam ver a resposta vazia (o `non_empty_answer` do `axon-generic`). O usuário
        # recebe um aviso em vez de uma resposta em branco (R50).
        _writer()({"kind": TOKEN, "text": EMPTY_ANSWER})
        outcome = replace(outcome, answer=EMPTY_ANSWER)
        errors.append(
            ExecutionIssue(
                stage=STAGE_GENERATE,
                kind="EmptyAnswer",
                message="a geração não produziu texto; o usuário recebeu o aviso padrão",
                severity="notice",
            )
        )
    finished(STAGE_VALIDATE)
    return {"validation": outcome, "errors": errors}


def _emit_retrieval(
    request_id: str, retrieved: Sequence[Chunk], reranked: Sequence[Chunk], delivered: Sequence[Chunk]
) -> None:
    """Os trechos da execução, como a Turn View os projeta, no trace (009 Fase 6, research R15): é o que o harness de
    avaliação lê para medir recuperação e rerank. Identificador, score e proveniência; o texto só dos entregues (o
    que o modelo viu, para o juiz julgar a fidelidade — o trace o corta e redige). Sem trecho nenhum (o `chat`), nada a
    emitir."""
    if not (retrieved or reranked or delivered):
        return
    _context().trace.emit(
        Retrieval(
            request_id=request_id,
            retrieved=tuple(_retrieved(chunk) for chunk in retrieved),
            reranked=tuple(_retrieved(chunk) for chunk in reranked),
            delivered=tuple(_retrieved(chunk, text=True) for chunk in delivered),
        )
    )


def _retrieved(chunk: Chunk, *, text: bool = False) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        score=chunk.score,
        document=chunk.document,
        version=chunk.version,
        status=chunk.status,
        section=chunk.section,
        page=chunk.page,
        text=chunk.text if text else None,
    )


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
