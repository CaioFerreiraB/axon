"""Testes do pack de teste: só axon_ai_contracts e o kit de testes, sem nenhum componente do core (US1, SC-003).

Rodam sem pytest-asyncio: hooks assíncronos são chamados com `asyncio.run`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from axon_ai_contracts import RETRIEVAL_TOOL_PARAMETERS, TurnView, retrieval_tool_spec
from axon_ai_contracts.testing import (
    REFERENCE_TIME,
    assert_pack_conforms,
    pack_context,
    tool_invocation,
    turn_view,
    validator_context,
)
from contract_test_pack.pack import ContractTestPack


def test_pack_conforms() -> None:
    assert_pack_conforms(ContractTestPack(), views=[turn_view(question="pergunta de exemplo", answer="resposta")])


def test_capabilities_are_enumerable() -> None:
    pack = ContractTestPack()
    ctx = pack_context(pack.name)
    assert pack.system_prompt(ctx)
    [tool] = pack.tools(ctx)
    assert (tool.name, tool.kind, tool.mutates) == ("echo", "native", False)
    assert tool.description and tool.parameters["type"] == "object"
    [named] = pack.retrievers(ctx)
    assert (named.name, named.collections) == ("docs", frozenset({"test_docs"}))
    assert pack.reranker(ctx) is not None
    assert [validator.name for validator in pack.validators(ctx)] == ["non_empty_answer"]


def test_derived_retrieval_tool() -> None:
    pack = ContractTestPack()
    [named] = pack.retrievers(pack_context(pack.name))
    spec = retrieval_tool_spec(named)
    assert (spec.kind, spec.name, spec.handler) == ("retrieval", "docs", None)
    assert spec.parameters == RETRIEVAL_TOOL_PARAMETERS


def test_native_tool_uses_reference_time() -> None:
    pack = ContractTestPack()
    [tool] = pack.tools(pack_context(pack.name))
    assert tool.handler is not None
    result = asyncio.run(tool.handler(tool_invocation({"text": "oi"})))
    assert result == {"arguments": {"text": "oi"}, "reference_time": REFERENCE_TIME.isoformat()}


def test_retriever_and_reranker() -> None:
    pack = ContractTestPack()
    ctx = pack_context(pack.name)
    [named] = pack.retrievers(ctx)
    found = asyncio.run(named.retriever.search("trecho", top_k=2))
    assert [item.chunk_id for item in found] == ["manual#1", "manual#2"]
    reranker = pack.reranker(ctx)
    assert reranker is not None
    assert len(asyncio.run(reranker.rerank("trecho", found, top_k=1))) == 1


def test_validator_flags_empty_answer() -> None:
    pack = ContractTestPack()
    [validator] = pack.validators(pack_context(pack.name))
    result = asyncio.run(validator.validate(turn_view(answer=" "), validator_context(pack.name)))
    assert not result.ok and result.flags == frozenset({"empty_answer"})


def test_prepare_context_uses_reference_time() -> None:
    pack = ContractTestPack()
    view = turn_view(question="q", reference_time=datetime(2023, 5, 1, 9, tzinfo=UTC))
    update = asyncio.run(pack.prepare_context(view, pack_context(pack.name)))
    assert update == {"seen_question": "q", "retrieval_filters": {"effective_on": "2023-05-01"}}


def test_same_result_with_two_turn_view_producers() -> None:
    """US4, teste independente: a Turn View da fixture e uma montada à mão dão o mesmo resultado."""
    pack = ContractTestPack()
    data = {"question": "pergunta", "messages": [{"role": "user", "content": "pergunta"}], "own_slice": {"a": [1]}}
    from_fixture = turn_view(**data)  # type: ignore[arg-type]
    by_hand = TurnView(request_id="req-test", assistant="test-assistant", reference_time=REFERENCE_TIME, **data)  # type: ignore[arg-type]
    assert from_fixture == by_hand
    ctx = pack_context(pack.name)
    assert asyncio.run(pack.prepare_context(from_fixture, ctx)) == asyncio.run(pack.prepare_context(by_hand, ctx))
