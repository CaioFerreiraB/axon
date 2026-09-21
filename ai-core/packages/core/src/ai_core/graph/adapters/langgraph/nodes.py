"""Nós do grafo: finos por construção.

Cada nó delega a um seam (002, 006) ou a uma função pura de `domain/` e escreve no canal de stream. É esta magreza que
torna o grafo reescrevível: a lógica vive nos serviços, o grafo só ordena (ADR-001, SC-001).
"""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from ai_core.graph.adapters.langgraph.state import AgentContext, AgentState
from ai_core.graph.adapters.langgraph.view import turn_view
from ai_core.observability.api import ValidationRun
from ai_core_contracts import ChatMessage

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
    """Geração pelo papel `generation` (006), com os fragmentos de instrução dos packs (002).

    O progresso sai **antes** da primeira chamada: é o primeiro sinal que a SC-004 mede, e ele chega mesmo quando o
    modelo demora a produzir o primeiro token.
    """
    ctx = _context()
    writer = _writer()
    writer({"kind": PROGRESS, "stage": STAGE_GENERATE})

    messages: list[ChatMessage] = [
        {"role": "system", "content": prompt} for prompt in ctx.hooks.system_prompts(ctx.composition)
    ]
    messages.extend({"role": m["role"], "content": m["content"]} for m in state.get("messages", ()))

    pieces: list[str] = []
    async for chunk in ctx.router.for_role("generation").stream(messages):
        text = chunk["delta"]
        if text:
            pieces.append(text)
            writer({"kind": TOKEN, "text": text})
    return {"answer": "".join(pieces)}


async def validate_answer(state: AgentState) -> dict[str, Any]:
    """Validators dos packs, em sequência (002). Não chamam modelos e não decidem se a execução falhou."""
    ctx = _context()
    _writer()({"kind": PROGRESS, "stage": STAGE_VALIDATE})
    outcome = await ctx.hooks.validate(ctx.composition, turn_view(state), state.get("packs", {}))
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
    return {"validation": outcome}
