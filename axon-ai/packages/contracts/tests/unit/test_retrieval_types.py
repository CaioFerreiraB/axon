from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from axon_ai_contracts._freeze import JSONValue
from axon_ai_contracts.retrieval import Chunk, NamedRetriever, Reranker, Retriever


class _Retriever:
    async def search(
        self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None
    ) -> Sequence[Chunk]:
        return ()


class _Reranker:
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return tuple(documents)[:top_k]


def test_chunk_defaults_and_invariants() -> None:
    chunk = Chunk(chunk_id="doc#1", text="t", score=0.5, document="doc", metadata={"tags": ["a"]})
    assert (chunk.version, chunk.status, chunk.section, chunk.page) == (None, None, None, None)
    assert chunk.metadata == {"tags": ("a",)}
    with pytest.raises(ValueError):
        Chunk(chunk_id="", text="t", score=0.0, document="doc")
    with pytest.raises(ValueError):
        Chunk(chunk_id="c", text="t", score=0.0, document=" ")
    with pytest.raises(ValueError):
        Chunk(chunk_id="c", text="t", score=0.0, document="doc", page=0)


def test_protocols_are_runtime_checkable() -> None:
    assert isinstance(_Retriever(), Retriever)
    assert isinstance(_Reranker(), Reranker)
    assert not isinstance(object(), Retriever)


def test_named_retriever_normalizes_collections() -> None:
    named = NamedRetriever(name="docs", description="Busca.", collections=["a", "b"], retriever=_Retriever())  # type: ignore[arg-type]
    assert named.collections == frozenset({"a", "b"})


@pytest.mark.parametrize("collections", [frozenset(), ["", "x"]])
def test_named_retriever_requires_collections(collections: object) -> None:
    with pytest.raises(ValueError):
        NamedRetriever(name="docs", description="Busca.", collections=collections, retriever=_Retriever())  # type: ignore[arg-type]


def test_named_retriever_rejects_text_as_collections() -> None:
    with pytest.raises(TypeError):
        NamedRetriever(name="docs", description="Busca.", collections="docs", retriever=_Retriever())  # type: ignore[arg-type]
