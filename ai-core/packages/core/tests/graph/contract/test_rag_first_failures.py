"""T071 — falhas e degradações do `rag_first` (research R37, R38; princípio VII).

Recuperação que falha encerra com `error`, sem gerar; rerank que falha ou foge do contrato degrada para a ordem do
retriever com `notice`; catálogo sem recuperação é "sem resultado". Não importa o framework de grafo (SC-001).
"""

from __future__ import annotations

from typing import Any

import pytest
from graph_testkit import (
    ANSWER,
    FakeSession,
    RecordingTraceSink,
    ScriptedHooks,
    ScriptedReranker,
    catalog_tool,
    chunk,
    docs_session,
    rag,
    rag_run,
    retrieval_tool,
)

from ai_core.graph.api import FinalEvent
from ai_core.observability.api import CoverageGate, ExecutionError, ExecutionFinished, ModelCall

pytestmark = pytest.mark.us3

CHUNKS = tuple(chunk(f"c{n}", score=0.9 - n * 0.05) for n in range(8))


async def final(events: Any) -> FinalEvent:
    collected = [event async for event in events]
    assert isinstance(collected[-1], FinalEvent)
    return collected[-1]


def kinds(final: FinalEvent) -> list[tuple[str, str, str]]:
    return [(issue.kind, issue.severity, issue.stage) for issue in final.errors]


def delivered(llm: Any) -> list[str]:
    """Os ids que a geração recebeu, na ordem."""
    (generation,) = llm.calls
    tools = [message["content"] for message in generation["messages"] if message["role"] == "tool"]
    return [line.split("· id: ")[1].rstrip("]") for text in tools for line in text.splitlines() if "· id: " in line]


# --- recuperação que falha → error, sem gerar -------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["error", "timeout"])
async def test_recuperacao_que_falha_encerra_sem_gerar(status: str) -> None:
    trace = RecordingTraceSink()
    hk = ScriptedHooks()
    session = docs_session(CHUNKS, failures={"docs.search": (status, "índice fora do ar")})
    events, _controller, _caps, llm = rag_run(session=session, hooks=hk, trace=trace)
    result = await final(events)

    assert result.answer == ""
    (issue,) = [i for i in result.errors if i.kind == "RetrievalFailed"]
    assert (issue.severity, issue.stage) == ("error", "retrieve")
    assert "docs.search" in issue.message and "índice fora do ar" in issue.message
    assert [(e.stage, e.kind) for e in trace.of_type(ExecutionError)] == [("retrieve", "RetrievalFailed")]
    assert trace.of_type(ModelCall) == [] and llm.calls == []
    assert hk.validate_views == []
    assert trace.of_type(CoverageGate) == []
    (finished,) = trace.of_type(ExecutionFinished)
    assert finished.ok is False


async def test_depois_da_falha_as_outras_tools_nao_rodam() -> None:
    session = FakeSession(
        (retrieval_tool("docs.search"), retrieval_tool("docs.outra")),
        chunks={"docs.outra": CHUNKS},
        failures={"docs.search": ("error", "quebrou")},
    )
    events, _controller, caps, _llm = rag_run(session=session)
    await final(events)
    assert [call.name for call in caps.session.calls] == ["docs.search"]


# --- rerank -----------------------------------------------------------------------------------------------------------


async def test_reranker_que_levanta_vale_a_ordem_do_retriever() -> None:
    hk = ScriptedHooks(rerankers={"docs": ScriptedReranker(error=RuntimeError("modelo de rerank ausente"))})
    events, _controller, _caps, llm = rag_run(session=docs_session(CHUNKS), hooks=hk)
    result = await final(events)
    (issue,) = [i for i in result.errors if i.kind == "RerankFailed"]
    assert (issue.severity, issue.stage) == ("notice", "rerank") and "'docs'" in issue.message
    assert delivered(llm) == [item.chunk_id for item in CHUNKS[:5]]


@pytest.mark.parametrize(
    "extra",
    [(chunk("estranho", 0.99),), (CHUNKS[6],)],
    ids=["trecho-que-nao-veio-da-recuperacao", "mais-que-top_k"],
)
async def test_reranker_fora_do_contrato_vale_a_ordem_do_retriever(extra: Any) -> None:
    reranker = ScriptedReranker(order=[item.chunk_id for item in reversed(CHUNKS)], extra=extra)
    events, _controller, _caps, llm = rag_run(
        session=docs_session(CHUNKS), hooks=ScriptedHooks(rerankers={"docs": reranker})
    )
    result = await final(events)
    assert ("RerankFailed", "notice", "rerank") in kinds(result)
    assert delivered(llm) == [item.chunk_id for item in CHUNKS[:5]]


async def test_pack_sem_reranker_leva_os_primeiros_sem_registro() -> None:
    events, _controller, _caps, llm = rag_run(session=docs_session(CHUNKS))
    result = await final(events)
    assert delivered(llm) == [item.chunk_id for item in CHUNKS[:5]]
    assert "RerankFailed" not in [kind for kind, _, _ in kinds(result)]


async def test_reranker_reordena() -> None:
    reranker = ScriptedReranker(order=["c7", "c3", "c1"])
    events, _controller, _caps, llm = rag_run(
        session=docs_session(CHUNKS), hooks=ScriptedHooks(rerankers={"docs": reranker})
    )
    await final(events)
    assert delivered(llm) == ["c7", "c3", "c1"]


# --- catálogo ---------------------------------------------------------------------------------------------------------


async def test_catalogo_sem_recuperacao_e_sem_resultado() -> None:
    trace = RecordingTraceSink()
    session = FakeSession((catalog_tool(),))
    events, controller, _caps, _llm = rag_run(session=session, grant=rag(controller=True), trace=trace, script=[ANSWER])
    await final(events)
    (gate,) = trace.of_type(CoverageGate)
    assert (gate.candidates, gate.passages, gate.best_score, gate.route) == (0, 0, None, "controller")
    assert len(controller.calls) == 1


async def test_mcp_indisponivel_e_registrado_como_no_agentic() -> None:
    session = docs_session(CHUNKS, unavailable={"fin": "fora do ar"})
    events, _controller, _caps, llm = rag_run(session=session)
    result = await final(events)
    assert [(i.severity, i.message) for i in result.errors if i.kind == "McpUnavailable"] == [
        ("error", "MCP 'fin': fora do ar")
    ]
    assert len(llm.calls) == 1


async def test_com_controller_e_catalogo_vazio_nao_escala() -> None:
    trace = RecordingTraceSink()
    events, controller, _caps, llm = rag_run(session=FakeSession(()), grant=rag(controller=True), trace=trace)
    result = await final(events)
    (gate,) = trace.of_type(CoverageGate)
    assert gate.route == "fallback"
    assert ("CoverageInsufficient", "notice", "gate") in kinds(result)
    (issue,) = [i for i in result.errors if i.kind == "CoverageInsufficient"]
    assert "não há tool para o loop" in issue.message
    assert controller.calls == [] and len(llm.calls) == 1
