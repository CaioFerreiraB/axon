"""T083 — validação no `rag_first` (US4 cenários 1 e 2; research R42, R43).

Os validators recebem a Turn View com o `generation_context` igual aos trechos entregues à geração — inclusive depois
do corte por posição no teto de contexto. Não importa o framework de grafo (SC-001).
"""

from __future__ import annotations

from typing import Any

import pytest
from graph_testkit import (
    MESSAGES,
    QUESTION,
    ScriptedHooks,
    chunk,
    docs_session,
    fenced,
    rag,
    rag_run,
    rendered,
)

from ai_core.assistants.api import Limits
from ai_core.capabilities.api import FencedToolResult, ToolCall
from ai_core.graph.api import FinalEvent
from ai_core.graph.domain.budget import estimate_tokens
from ai_core.graph.domain.transcript import ToolStep, generation_messages

pytestmark = pytest.mark.us4

PROMPTS = ("Prompt do pack.",)
CHUNKS = tuple(chunk(f"c{n}", score=0.9 - n * 0.05, text="t" * 300) for n in range(5))


async def run(**kwargs: Any) -> tuple[FinalEvent, ScriptedHooks, Any]:
    hooks = ScriptedHooks(prompts=PROMPTS)
    events, _controller, _caps, llm = rag_run(session=docs_session(CHUNKS), hooks=hooks, **kwargs)
    collected = [event async for event in events]
    assert isinstance(collected[-1], FinalEvent)
    return collected[-1], hooks, llm


def ceiling_for(kept: int) -> int:
    """O teto exato em que só os `kept` primeiros trechos cabem na geração (a estimativa do `budget.py`)."""
    steps = []
    if kept:
        result = FencedToolResult(
            name="docs.search", kind="retrieval", status="ok", text=fenced("docs.search", rendered(CHUNKS[:kept]))
        )
        steps = [ToolStep(iteration=1, call=ToolCall(name="docs.search", arguments={"query": QUESTION}), result=result)]
    return estimate_tokens(generation_messages(PROMPTS, MESSAGES, steps))


def ids(chunks: Any) -> list[str]:
    return [item.chunk_id for item in chunks]


async def test_validators_recebem_os_trechos_entregues_na_ordem() -> None:
    final, hooks, _llm = await run()
    (view,) = hooks.validate_views
    assert ids(view.generation_context) == ids(CHUNKS)
    assert ids(view.reranked) == ids(CHUNKS) and ids(view.retrieved) == ids(CHUNKS)
    (stream_view,) = hooks.stream_views
    assert ids(stream_view.generation_context) == ids(CHUNKS), "o filtro de streaming vê o mesmo contexto"
    assert "ContextTrimmed" not in [issue.kind for issue in final.errors]


async def test_teto_tira_os_trechos_de_menor_posicao() -> None:
    final, hooks, llm = await run(grant=rag(limits=Limits(max_context_tokens=ceiling_for(3))))
    (view,) = hooks.validate_views
    assert ids(view.generation_context) == ["c0", "c1", "c2"]
    (generation,) = llm.calls
    (tool_message,) = [message for message in generation["messages"] if message["role"] == "tool"]
    assert "id: c3]" not in tool_message["content"] and "id: c4]" not in tool_message["content"]
    (trimmed,) = [issue for issue in final.errors if issue.kind == "ContextTrimmed"]
    assert trimmed.severity == "notice" and trimmed.stage == "gate" and "2 trecho(s)" in trimmed.message


async def test_teto_que_nao_comporta_nenhum_trecho() -> None:
    final, hooks, llm = await run(grant=rag(limits=Limits(max_context_tokens=ceiling_for(0))))
    (view,) = hooks.validate_views
    assert tuple(view.generation_context) == ()
    (generation,) = llm.calls
    assert [message for message in generation["messages"] if message["role"] == "tool"] == []
    (trimmed,) = [issue for issue in final.errors if issue.kind == "ContextTrimmed"]
    assert "5 trecho(s)" in trimmed.message
