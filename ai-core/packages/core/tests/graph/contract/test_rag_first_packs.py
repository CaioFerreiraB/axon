"""T072 — composição de dois packs no `rag_first` (research R38, R41; premissa da spec sobre vários packs)."""

from __future__ import annotations

import json
from itertools import pairwise
from typing import Any

import pytest
from graph_testkit import (
    QUESTION,
    FakeSession,
    ScriptedHooks,
    ScriptedReranker,
    chunk,
    rag,
    rag_run,
    retrieval_tool,
)

from ai_core.graph.api import FinalEvent, RagSettings
from ai_core.packs.api import Composition

pytestmark = pytest.mark.us3

A = (chunk("a1", 0.6), chunk("a2", 0.95))
B = (chunk("b1", 0.8), chunk("b2", 0.7))


def setup(settings: RagSettings) -> tuple[Any, ScriptedReranker, ScriptedReranker, Any]:
    session = FakeSession(
        (retrieval_tool("a.search"), retrieval_tool("b.search")), chunks={"a.search": A, "b.search": B}
    )
    ra, rb = ScriptedReranker(order=["a2", "a1"]), ScriptedReranker(order=["b2", "b1"])
    events, _controller, _caps, llm = rag_run(
        session=session,
        grant=rag(composition=Composition(packs=("a", "b"))),
        hooks=ScriptedHooks(rerankers={"a": ra, "b": rb}),
        settings=settings,
    )
    return events, ra, rb, llm


def pairs(llm: Any) -> list[tuple[str, list[str]]]:
    """(tool chamada, ids no resultado) de cada passo que a geração recebeu."""
    (generation,) = llm.calls
    messages = generation["messages"]
    found = []
    for call, result in pairwise(messages):
        if call["role"] == "assistant" and call.get("tool_calls") and result["role"] == "tool":
            (tool_call,) = call["tool_calls"]
            assert json.loads(tool_call["arguments"]) == {"query": QUESTION}
            ids = [line.split("· id: ")[1].rstrip("]") for line in result["content"].splitlines() if "· id: " in line]
            found.append((tool_call["name"], ids))
    return found


async def test_cada_reranker_recebe_so_o_seu_pack_e_a_juncao_respeita_as_ordens() -> None:
    events, ra, rb, llm = setup(RagSettings(passages=3))
    collected = [event async for event in events]
    assert isinstance(collected[-1], FinalEvent)
    assert [documents for _, documents, _ in ra.calls] == [A]
    assert [documents for _, documents, _ in rb.calls] == [B]
    assert pairs(llm) == [("a.search", ["a2"]), ("b.search", ["b2", "b1"])]


async def test_pack_sem_trecho_entregue_nao_tem_passo() -> None:
    events, _ra, _rb, llm = setup(RagSettings(passages=1))
    _ = [event async for event in events]
    assert pairs(llm) == [("a.search", ["a2"])]
