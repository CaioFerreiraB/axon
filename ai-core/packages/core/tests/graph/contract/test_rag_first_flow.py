"""T070 — conformidade do flow `rag_first` (US3 cenários 1 a 4, SC-003; contracts/rag-first-flow.md).

Gateway falso da 004 com a tool de recuperação `docs.search`, Pack Hooks com reranker programado, controller no roteador
real da 006. Não importa o framework de grafo (SC-001).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from graph_testkit import (
    ANSWER,
    QUESTION,
    RecordingTraceSink,
    ScriptedHooks,
    ScriptedReranker,
    chunk,
    docs_session,
    rag,
    rag_run,
    tool_action,
)

from ai_core.assistants.api import Limits
from ai_core.capabilities.api import FENCE_INSTRUCTION, ToolCall
from ai_core.graph.api import FinalEvent, ProgressEvent, RagSettings
from ai_core.observability.api import CoverageGate, ModelCall
from axon_ai_contracts import RETRIEVAL_FILTERS_KEY

pytestmark = pytest.mark.us3

CHUNKS = tuple(chunk(f"doc#c{n}", score=round(0.9 - n * 0.05, 2), section=f"Seção {n}", page=n + 1) for n in range(8))
IDENTITY = [item.chunk_id for item in CHUNKS]


async def collect(events: Any) -> list[Any]:
    return [event async for event in events]


def final_of(events: list[Any]) -> FinalEvent:
    assert isinstance(events[-1], FinalEvent)
    assert sum(isinstance(event, FinalEvent) for event in events) == 1
    return events[-1]


def kinds(final: FinalEvent) -> list[tuple[str, str, str]]:
    return [(issue.kind, issue.severity, issue.stage) for issue in final.errors]


def hooks(**kwargs: Any) -> ScriptedHooks:
    return ScriptedHooks(prompts=("Prompt do pack.",), **kwargs)


# --- cen. 1 e SC-003: coberto → uma chamada de modelo -----------------------------------------------------------------


async def test_caminho_coberto_gera_com_uma_unica_chamada_de_modelo() -> None:
    trace = RecordingTraceSink()
    reranker = ScriptedReranker(order=IDENTITY)
    events, controller, caps, llm = rag_run(
        session=docs_session(CHUNKS), hooks=hooks(rerankers={"docs": reranker}), trace=trace
    )
    events = await collect(events)
    final = final_of(events)

    assert [issue for issue in final.errors if issue.severity == "error"] == []
    assert caps.session.calls == [ToolCall(name="docs.search", arguments={"query": QUESTION, "top_k": 20})]
    ((query, documents, top_k),) = reranker.calls
    assert (query, documents, top_k) == (QUESTION, CHUNKS, 5)

    assert [call.role for call in trace.of_type(ModelCall)] == ["generation"], "SC-003"
    assert controller.calls == []

    (generation,) = llm.calls
    messages = generation["messages"]
    assert messages[0] == {"role": "system", "content": "Prompt do pack."}
    assert messages[1] == {"role": "system", "content": FENCE_INSTRUCTION}
    assert messages[2] == {"role": "user", "content": QUESTION}
    assert messages[3]["role"] == "assistant"
    ((call,),) = [messages[3]["tool_calls"]]
    assert call["name"] == "docs.search" and json.loads(call["arguments"]) == {"query": QUESTION}
    assert messages[4]["role"] == "tool" and messages[4]["tool_call_id"] == call["id"]
    assert len(messages) == 5
    for item in CHUNKS[:5]:
        assert f"· id: {item.chunk_id}]" in messages[4]["content"], "ADR-026"
    for item in CHUNKS[5:]:
        assert item.chunk_id not in messages[4]["content"]

    (gate,) = trace.of_type(CoverageGate)
    assert (gate.covered, gate.route, gate.candidates, gate.passages, gate.threshold) == (True, "generate", 8, 5, None)
    assert gate.best_score == CHUNKS[0].score

    stages = [event.stage for event in events if isinstance(event, ProgressEvent)]
    assert stages == ["prepare_context", "retrieve", "rerank", "gate", "generate", "validate_answer"]


async def test_coberto_com_limiar_quando_o_melhor_score_alcanca() -> None:
    trace = RecordingTraceSink()
    events, controller, _caps, _llm = rag_run(
        session=docs_session((chunk("a", 0.8), chunk("b", 0.4))),
        trace=trace,
        grant=rag(controller=True),
        settings=RagSettings(min_score=0.5),
    )
    final_of(await collect(events))
    (gate,) = trace.of_type(CoverageGate)
    assert (gate.covered, gate.route, gate.threshold, gate.best_score) == (True, "generate", 0.5, 0.8)
    assert controller.calls == []


# --- cen. 2: sem cobertura, com controller → loop ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("chunks", "settings"),
    [((), None), ((chunk("abaixo-1", 0.8), chunk("abaixo-2", 0.7)), RagSettings(min_score=0.9))],
    ids=["sem-resultado", "abaixo-do-limiar"],
)
async def test_sem_cobertura_com_controller_escala_para_o_loop(chunks: Any, settings: Any) -> None:
    trace = RecordingTraceSink()
    events, controller, _caps, llm = rag_run(
        session=docs_session(chunks), grant=rag(controller=True), trace=trace, settings=settings, script=[ANSWER]
    )
    final = final_of(await collect(events))

    assert len(controller.calls) == 1
    enviado = json.dumps(controller.calls[0]["messages"], ensure_ascii=False)
    assert not any(message["role"] == "tool" for message in controller.calls[0]["messages"]), "transcrição vazia"
    assert "abaixo-1" not in enviado and "abaixo-2" not in enviado
    (gate,) = trace.of_type(CoverageGate)
    assert (gate.covered, gate.route) == (False, "controller")
    assert "CoverageInsufficient" not in [kind for kind, _, _ in kinds(final)]
    assert len(llm.calls) == 1


async def test_loop_escalado_respeita_o_limite_do_grant() -> None:
    script = [tool_action("docs.search", query="outra"), tool_action("docs.search", query="mais uma")]
    events, controller, caps, _llm = rag_run(
        session=docs_session(()), grant=rag(controller=True, limits=Limits(max_iterations=2)), script=script
    )
    final = final_of(await collect(events))
    assert len(controller.calls) == 2
    assert [call.arguments["query"] for call in caps.session.calls] == [QUESTION, "outra", "mais uma"]
    assert ("IterationLimit", "notice", "controller") in kinds(final)


# --- cen. 3: sem cobertura, sem controller → geração sem trechos ------------------------------------------------------


@pytest.mark.parametrize(
    ("chunks", "settings"),
    [((), None), ((chunk("abaixo", 0.8),), RagSettings(min_score=0.9))],
    ids=["sem-resultado", "abaixo-do-limiar"],
)
async def test_sem_cobertura_sem_controller_gera_sem_trechos(chunks: Any, settings: Any) -> None:
    trace = RecordingTraceSink()
    hk = hooks()
    events, controller, _caps, llm = rag_run(session=docs_session(chunks), hooks=hk, trace=trace, settings=settings)
    final = final_of(await collect(events))

    (generation,) = llm.calls
    roles = [message["role"] for message in generation["messages"]]
    assert "tool" not in roles and FENCE_INSTRUCTION not in [m.get("content") for m in generation["messages"]]
    assert ("CoverageInsufficient", "notice", "gate") in kinds(final)
    (issue,) = [i for i in final.errors if i.kind == "CoverageInsufficient"]
    assert "o Assistant não tem controller" in issue.message
    assert [issue for issue in final.errors if issue.severity == "error"] == []
    (gate,) = trace.of_type(CoverageGate)
    assert (gate.covered, gate.route) == (False, "fallback")
    assert hk.validate_views[-1].generation_context == ()
    assert controller.calls == []


# --- cen. 4: filtros do pack chegam aos retrievers sem leitura --------------------------------------------------------


async def test_filtros_publicados_pelo_pack_vao_intactos_ao_gateway() -> None:
    filtros = {"effective_from": "2026-10-09", "branch": "qualquer", "aninhado": {"x": [1, 2]}}
    hk = hooks(slice_update={RETRIEVAL_FILTERS_KEY: filtros, "outro": "dado"})
    events, _controller, caps, _llm = rag_run(session=docs_session(CHUNKS), hooks=hk)
    final_of(await collect(events))
    ((_grant, context),) = caps.opened
    assert dict(context.retrieval_filters) == {"docs": filtros}
