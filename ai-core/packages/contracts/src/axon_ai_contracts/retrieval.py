"""Recuperação: chunks com proveniência, retrievers nomeados e reranker (FR-006, FR-007, research R9)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Protocol, runtime_checkable

from axon_ai_contracts._freeze import JSONValue, empty_mapping, freeze_mapping, require_non_empty
from axon_ai_contracts.tools import ToolSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class Chunk:
    """Trecho recuperado com proveniência e vigência (princípio IX). `status` tem semântica definida pelo pack."""

    chunk_id: str
    text: str
    score: float
    document: str
    version: str | None = None
    status: str | None = None
    section: str | None = None
    page: int | None = None
    metadata: Mapping[str, JSONValue] = field(default_factory=empty_mapping)

    def __post_init__(self) -> None:
        require_non_empty("chunk_id", self.chunk_id)
        require_non_empty("document", self.document)
        if self.page is not None and self.page < 1:
            raise ValueError("page precisa ser >= 1")
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))


@runtime_checkable
class Retriever(Protocol):
    """Busca por consulta. `filters` vem só de `retrieval_filters` da fatia do próprio pack, nunca do modelo."""

    async def search(
        self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None
    ) -> Sequence[Chunk]: ...


@runtime_checkable
class Reranker(Protocol):
    """Devolve no máximo `top_k` chunks, reordenados, todos vindos de `documents`."""

    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class NamedRetriever:
    """Retriever declarado pelo pack. Com as coleções, o core o deixa fora do catálogo se o grant não as tiver."""

    name: str
    description: str
    collections: frozenset[str]
    retriever: Retriever

    def __post_init__(self) -> None:
        require_non_empty("name", self.name)
        require_non_empty("description", self.description)
        collections: Iterable[str] = self.collections
        if isinstance(collections, str):
            raise TypeError("collections precisa ser uma coleção de nomes, não um texto")
        frozen = frozenset(collections)
        if not frozen or any(not isinstance(name, str) or not name.strip() for name in frozen):
            raise ValueError("um retriever precisa declarar ao menos uma coleção, com nome não vazio")
        object.__setattr__(self, "collections", frozen)


RETRIEVAL_TOOL_PARAMETERS: Final[Mapping[str, JSONValue]] = freeze_mapping(
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "top_k": {"type": "integer", "minimum": 1},
        },
        "required": ["query"],
        "additionalProperties": False,
    }
)
"""Esquema padrão das tools `retrieval`: o modelo escolhe a consulta e, opcionalmente, a quantidade — nunca filtros."""


def retrieval_tool_spec(named: NamedRetriever) -> ToolSpec:
    """A tool `retrieval` que o core deriva de um retriever nomeado (FR-006, ADR-005)."""
    return ToolSpec(
        name=named.name,
        description=named.description,
        parameters=RETRIEVAL_TOOL_PARAMETERS,
        kind="retrieval",
        mutates=False,
        handler=None,
    )
