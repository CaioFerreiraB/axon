"""Conformidade: hooks de catálogo, declaração e validators (FR-007, FR-019; T029)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from packs import make_pack

from ai_core_contracts import (
    Chunk,
    NamedRetriever,
    PackContext,
    ToolInvocation,
    ToolSpec,
    TurnView,
    ValidationResult,
    ValidatorContext,
)
from ai_core_contracts.testing import check_pack, chunk


def _codes(pack: object) -> list[str]:
    return [issue.code for issue in check_pack(pack, check_distribution=False).issues]


def test_catalog_hooks_are_called_exactly_once() -> None:
    calls: list[str] = []

    def recorder(hook: str, result: Any) -> Any:
        def method(self: Any, ctx: PackContext) -> Any:
            calls.append(hook)
            return result

        return method

    pack = make_pack(
        system_prompt=recorder("system_prompt", "texto"),
        tools=recorder("tools", ()),
        retrievers=recorder("retrievers", ()),
        reranker=recorder("reranker", None),
        validators=recorder("validators", ()),
    )
    assert _codes(pack) == []
    assert sorted(calls) == ["reranker", "retrievers", "system_prompt", "tools", "validators"]


def test_wrong_return_type() -> None:
    pack = make_pack(tools=lambda self, ctx: [{"name": "echo"}])
    assert _codes(pack) == ["hook.return_type"]
    assert _codes(make_pack(system_prompt=lambda self, ctx: 42)) == ["hook.return_type"]


def test_retriever_without_collection_raises_inside_hook() -> None:
    class _Retriever:
        async def search(self, query: str, **kwargs: Any) -> Sequence[Chunk]:
            return ()

    def retrievers(self: Any, ctx: PackContext) -> tuple[NamedRetriever, ...]:
        return (NamedRetriever(name="docs", description="d", collections=frozenset(), retriever=_Retriever()),)

    report = check_pack(make_pack(retrievers=retrievers), check_distribution=False)
    [issue] = report.issues
    assert (issue.code, issue.subject) == ("hook.raised", "hook:retrievers")


class _SyncReranker:
    def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return documents


class _GreedyReranker:
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return tuple(documents)


class _InventingReranker:
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return (chunk("inventado"),)


class _GoodReranker:
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return tuple(reversed(documents))[:top_k]


def test_reranker_contract() -> None:
    [issue] = check_pack(make_pack(reranker=lambda self, ctx: _SyncReranker()), check_distribution=False).issues
    assert (issue.code, issue.subject) == ("hook.not_async", "reranker")
    assert _codes(make_pack(reranker=lambda self, ctx: _GreedyReranker())) == ["reranker.contract"]
    assert _codes(make_pack(reranker=lambda self, ctx: _InventingReranker())) == ["reranker.contract"]
    assert _codes(make_pack(reranker=lambda self, ctx: _GoodReranker())) == []


async def _handler(invocation: ToolInvocation) -> object:
    return None


def test_declaration_issues_are_reported() -> None:
    def tools(self: Any, ctx: PackContext) -> tuple[ToolSpec, ...]:
        spec = ToolSpec(name="echo", description="d", parameters={"type": "object"}, kind="native", handler=_handler)
        return (spec, spec)

    assert _codes(make_pack(tools=tools)) == ["tool.duplicate_name"]


class _WrongResultValidator:
    name = "errado"

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> Any:
        return {"ok": True}


class _CountingValidator:
    name = "contador"

    def __init__(self) -> None:
        self.count = 0

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        self.count += 1
        return ValidationResult(ok=True, issues=(str(self.count),))


def test_validators_must_return_result_and_be_deterministic() -> None:
    assert _codes(make_pack(validators=lambda self, ctx: (_WrongResultValidator(),))) == ["validator.result_type"]
    assert _codes(make_pack(validators=lambda self, ctx: (_CountingValidator(),))) == ["validator.non_deterministic"]
