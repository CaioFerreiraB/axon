"""O motor emite `Retrieval` na validação (spec 009 Fase 6, research R15; T023): os trechos candidatos, reordenados e
entregues, como a Turn View os projeta — o que o harness de avaliação lê. Não importa o framework de grafo (SC-001)."""

from __future__ import annotations

from typing import Any

import pytest
from graph_testkit import (
    ANSWER,
    FakeCapabilities,
    FakeSession,
    RecordingTraceSink,
    ScriptedController,
    ScriptedHooks,
    ScriptedReranker,
    agentic,
    chunk,
    docs_session,
    engine,
    rag_run,
    request,
    retrieval_tool,
    tool_action,
)

from ai_core.graph.api import FinalEvent, RagSettings
from ai_core.observability.api import Retrieval, ValidationRun

pytestmark = pytest.mark.us2

CHUNKS = tuple(
    chunk(f"doc#c{n}", score=0.9 - n * 0.1, document="Regulamento", section=f"Seção {n}", page=n + 1) for n in range(4)
)


async def drain(events: Any) -> list[Any]:
    collected = [event async for event in events]
    assert isinstance(collected[-1], FinalEvent)
    return collected


def ids(items: Any) -> list[str]:
    return [item.chunk_id for item in items]


async def test_rag_first_coberto_emite_candidatos_juncao_e_entregues() -> None:
    trace = RecordingTraceSink()
    reranker = ScriptedReranker(order=["doc#c2", "doc#c0", "doc#c1"])
    events, _controller, _caps, _llm = rag_run(
        session=docs_session(CHUNKS),
        hooks=ScriptedHooks(rerankers={"docs": reranker}),
        trace=trace,
        settings=RagSettings(passages=3),
    )
    await drain(events)
    (evento,) = trace.of_type(Retrieval)
    assert ids(evento.retrieved) == ["doc#c0", "doc#c1", "doc#c2", "doc#c3"]
    assert ids(evento.reranked) == ["doc#c2", "doc#c0", "doc#c1"]
    assert ids(evento.delivered) == ["doc#c2", "doc#c0", "doc#c1"]
    primeiro = evento.retrieved[0]
    assert (primeiro.document, primeiro.section, primeiro.page, primeiro.score) == ("Regulamento", "Seção 0", 1, 0.9)
    assert primeiro.text is None and evento.reranked[0].text is None
    assert [c.text for c in evento.delivered] == ["texto de doc#c2", "texto de doc#c0", "texto de doc#c1"]
    ordem = [type(e).__name__ for e in trace.events if isinstance(e, Retrieval | ValidationRun)]
    assert ordem[0] == "Retrieval", "sai antes dos validators"


async def test_chat_nao_emite() -> None:
    trace = RecordingTraceSink()
    await drain(engine(trace=trace).run(agentic(flow="chat"), request()))
    assert trace.of_type(Retrieval) == []


async def test_agentic_com_recuperacao_emite_os_trechos_do_loop() -> None:
    trace = RecordingTraceSink()
    session = FakeSession((retrieval_tool(),), chunks={"docs.search": CHUNKS[:2]})
    controller = ScriptedController([tool_action("docs.search", query="x"), ANSWER])
    motor = engine(capabilities=FakeCapabilities(session), controller=controller, trace=trace)
    await drain(motor.run(agentic(), request()))
    (evento,) = trace.of_type(Retrieval)
    assert ids(evento.retrieved) == ["doc#c0", "doc#c1"]
    assert evento.reranked == ()
    assert ids(evento.delivered) == ["doc#c0", "doc#c1"]
