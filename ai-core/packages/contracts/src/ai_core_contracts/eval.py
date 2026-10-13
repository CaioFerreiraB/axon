"""Avaliação: o que uma métrica de domínio lê e implementa (ADR-027; spec 009, Fase 6).

O harness da 009 roda um conjunto dourado contra um Assistant e mede recuperação, rerank, geração, citação e operação.
Métricas que só fazem sentido no domínio vêm do pack: ele as declara pelo hook opcional `eval_metrics` e o harness
chama `measure` item a item, com o que o item declara (`EvalItem`) e o que a execução produziu (`EvalObservation`).
Tudo aqui é dado puro — a métrica não vê o core, e o core não interpreta a métrica.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from ai_core_contracts._freeze import (
    JSONValue,
    empty_mapping,
    freeze_mapping,
    freeze_sequence,
    require_aware,
    require_non_empty,
)
from ai_core_contracts.pack import PackContext
from ai_core_contracts.view import Citation


@dataclass(frozen=True, slots=True, kw_only=True)
class EvalEvidence:
    """Uma evidência esperada: o documento (`Chunk.document`), com seção ou identificador de trecho opcionais.

    Declarada por documento para sobreviver a mudanças de chunking; o identificador, quando dado, casa com prioridade.
    """

    document: str
    section: str | None = None
    chunk_id: str | None = None

    def __post_init__(self) -> None:
        require_non_empty("document", self.document)
        if self.chunk_id is not None:
            require_non_empty("chunk_id", self.chunk_id)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvalItem:
    """Um item do conjunto dourado, como a métrica o lê. `extra` carrega campos de domínio, opacos para o core."""

    id: str
    question: str
    reference_time: datetime
    expected_documents: Sequence[EvalEvidence] = ()
    reference_answer: str | None = None
    expected_citations: Sequence[EvalEvidence] = ()
    extra: Mapping[str, JSONValue] = field(default_factory=empty_mapping)

    def __post_init__(self) -> None:
        require_non_empty("id", self.id)
        require_non_empty("question", self.question)
        try:
            require_aware("reference_time", self.reference_time)
        except TypeError as error:
            raise ValueError(str(error)) from error
        object.__setattr__(self, "expected_documents", freeze_sequence(self.expected_documents))
        object.__setattr__(self, "expected_citations", freeze_sequence(self.expected_citations))
        object.__setattr__(self, "extra", freeze_mapping(self.extra))


@dataclass(frozen=True, slots=True, kw_only=True)
class EvalChunk:
    """Um trecho observado na execução: identificador, score e a proveniência do `Chunk` — nunca o texto."""

    chunk_id: str
    score: float
    document: str
    version: str | None = None
    status: str | None = None
    section: str | None = None
    page: int | None = None

    def __post_init__(self) -> None:
        require_non_empty("chunk_id", self.chunk_id)
        require_non_empty("document", self.document)
        if math.isnan(self.score):
            raise ValueError("score não pode ser NaN")
        if self.page is not None and self.page < 1:
            raise ValueError("page precisa ser >= 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvalObservation:
    """O que a execução de um item produziu: resposta e citações finais, flags, os trechos candidatos (`retrieved`),
    reordenados (`reranked`) e entregues à geração (`delivered`), e os tipos dos registros."""

    answer: str
    citations: Sequence[Citation] = ()
    flags: frozenset[str] = frozenset()
    retrieved: Sequence[EvalChunk] = ()
    reranked: Sequence[EvalChunk] = ()
    delivered: Sequence[EvalChunk] = ()
    issue_kinds: Sequence[str] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", freeze_sequence(self.citations))
        object.__setattr__(self, "flags", frozenset(self.flags))
        for name in ("retrieved", "reranked", "delivered", "issue_kinds"):
            object.__setattr__(self, name, _tuple(getattr(self, name)))


def _tuple[T](items: Iterable[T]) -> tuple[T, ...]:
    return tuple(items)


@runtime_checkable
class EvalMetric(Protocol):
    """Métrica de domínio: valor por item, puro e síncrono; `None` quando não se aplica ao item.

    `better` diz o sentido da melhora (para a comparação com a linha de base); só métricas `deterministic` — que não
    dependem do texto gerado — podem barrar uma regressão no CI.
    """

    name: str
    better: Literal["higher", "lower"]
    deterministic: bool

    def measure(self, item: EvalItem, observation: EvalObservation) -> float | None: ...


@runtime_checkable
class ProvidesEvalMetrics(Protocol):
    """O hook opcional de um pack que declara métricas de domínio. Chamado uma vez, na carga, como os de catálogo."""

    def eval_metrics(self, ctx: PackContext) -> Sequence[EvalMetric]: ...
