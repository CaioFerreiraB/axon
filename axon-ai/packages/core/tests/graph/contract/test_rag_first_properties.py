"""T075 — propriedades do `rag_first` (hypothesis; SC-003, SC-005): para qualquer saída do retriever e qualquer limiar,
um evento final, no máximo uma chamada de geração, nenhuma do controller e `generation_context ⊆ reranked ⊆ retrieved`.
"""

from __future__ import annotations

import pytest
from graph_testkit import RecordingTraceSink, ScriptedHooks, chunk, docs_session, rag_run
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axon_ai.graph.api import FinalEvent, RagSettings
from axon_ai.observability.api import CoverageGate, ModelCall

pytestmark = pytest.mark.us3


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    scores=st.lists(st.floats(min_value=0, max_value=1, allow_nan=False), max_size=30),
    min_score=st.one_of(st.none(), st.floats(min_value=0, max_value=1, allow_nan=False)),
    passages=st.integers(min_value=1, max_value=8),
)
async def test_propriedades_sem_controller(scores: list[float], min_score: float | None, passages: int) -> None:
    trace = RecordingTraceSink()
    hooks = ScriptedHooks()
    chunks = tuple(chunk(f"c{n}", score) for n, score in enumerate(scores))
    events, controller, _caps, llm = rag_run(
        session=docs_session(chunks),
        hooks=hooks,
        trace=trace,
        settings=RagSettings(passages=passages, min_score=min_score),
    )
    collected = [event async for event in events]
    assert isinstance(collected[-1], FinalEvent)
    assert sum(isinstance(event, FinalEvent) for event in collected) == 1
    assert [call.role for call in trace.of_type(ModelCall)] == ["generation"] and len(llm.calls) == 1
    assert controller.calls == []

    view = hooks.validate_views[-1]
    retrieved = [c.chunk_id for c in view.retrieved]
    reranked = [c.chunk_id for c in view.reranked]
    context = [c.chunk_id for c in view.generation_context]
    assert set(context) <= set(reranked) <= set(retrieved)
    assert len(reranked) <= passages

    (gate,) = trace.of_type(CoverageGate)
    assert gate.covered == (gate.route == "generate") == bool(context)
