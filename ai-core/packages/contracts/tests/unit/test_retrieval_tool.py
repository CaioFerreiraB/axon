"""Invariantes de ToolSpec/NamedRetriever e a tool `retrieval` derivada (US2 cenários 3 e 4; T027)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from ai_core_contracts import (
    RETRIEVAL_TOOL_PARAMETERS,
    Chunk,
    JSONValue,
    NamedRetriever,
    ToolInvocation,
    ToolSpec,
    retrieval_tool_spec,
)


class _Retriever:
    async def search(
        self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None
    ) -> Sequence[Chunk]:
        return ()


async def _handler(invocation: ToolInvocation) -> object:
    return None


def test_native_without_handler_is_rejected() -> None:
    with pytest.raises(ValueError):
        ToolSpec(name="t", description="d", parameters={"type": "object"}, kind="native")


def test_retrieval_with_handler_is_rejected() -> None:
    with pytest.raises(ValueError):
        ToolSpec(name="t", description="d", parameters={"type": "object"}, kind="retrieval", handler=_handler)


def test_named_retriever_without_collection_is_rejected() -> None:
    with pytest.raises(ValueError):
        NamedRetriever(name="docs", description="Busca.", collections=frozenset(), retriever=_Retriever())


def test_derived_retrieval_tool() -> None:
    named = NamedRetriever(
        name="docs", description="Busca nos documentos.", collections=frozenset({"d"}), retriever=_Retriever()
    )
    spec = retrieval_tool_spec(named)
    assert spec.kind == "retrieval"
    assert (spec.name, spec.description) == ("docs", "Busca nos documentos.")
    assert spec.parameters == RETRIEVAL_TOOL_PARAMETERS
    assert spec.mutates is False
    assert spec.handler is None


def test_standard_retrieval_schema() -> None:
    assert RETRIEVAL_TOOL_PARAMETERS == {
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1}, "top_k": {"type": "integer", "minimum": 1}},
        "required": ("query",),
        "additionalProperties": False,
    }
    with pytest.raises(TypeError):
        RETRIEVAL_TOOL_PARAMETERS["type"] = "array"  # type: ignore[index]
