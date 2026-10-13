"""Seam do harness de avaliação (spec 009, Fase 6): formato de conjunto dourado, formato de relatório e `EvalHarness`.

Contrato em specs/009-core-observability-evaluation/contracts/eval-harness.md. Único módulo do `eval` que outros
importam; depende só da stdlib, de `ai_core_contracts` e do `api.py` da 003 (o `Principal` da rodada). O conjunto
dourado e o relatório sobrevivem a uma reescrita do harness — é o que torna as linhas de base comparáveis.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Final, Literal, Protocol

from ai_core.assistants.api import Principal
from ai_core_contracts import JSONValue

type Better = Literal["higher", "lower"]
"""O sentido em que a métrica melhora. `None` numa `MetricValue` = informativa, nunca regride."""

DEFAULT_K: Final = (5, 20)
DEFAULT_TOLERANCE: Final = 0.02
"""Tolerância absoluta das métricas determinísticas quando o conjunto dourado não diz outra (research R16)."""

_ITEM_ID: Final = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_BETTER: Final = frozenset({"higher", "lower"})


class GoldenSetError(ValueError):
    """O arquivo do conjunto dourado não pode ser usado (ilegível, sem `items`, `version` desconhecida)."""


class EvalInputError(ValueError):
    """A rodada não pode começar: Assistant inexistente ou indisponível, trace sem leitura, relatório ilegível."""


def _require_text(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} não pode ser vazio")


def _frozen(value: Mapping[str, JSONValue]) -> Mapping[str, JSONValue]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    """Evidência esperada: o documento do trecho, com seção ou identificador de trecho opcionais (clarificação 2)."""

    document: str
    section: str | None = None
    chunk_id: str | None = None

    def __post_init__(self) -> None:
        _require_text("document", self.document)
        if self.chunk_id is not None:
            _require_text("chunk_id", self.chunk_id)


@dataclass(frozen=True, slots=True, kw_only=True)
class GoldenItem:
    """Um item do conjunto dourado. `reference_time` fixa a data da execução (ADR-013); `extra` é opaco."""

    id: str
    question: str
    reference_time: datetime
    expected_documents: Sequence[Evidence] = ()
    reference_answer: str | None = None
    expected_citations: Sequence[Evidence] = ()
    extra: Mapping[str, JSONValue] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not _ITEM_ID.match(self.id):
            raise ValueError(f"id inválido: {self.id!r} (esperado ^[a-z0-9][a-z0-9._-]*$)")
        _require_text("question", self.question)
        if self.reference_time.tzinfo is None or self.reference_time.utcoffset() is None:
            raise ValueError("reference_time precisa ter fuso")
        object.__setattr__(self, "expected_documents", tuple(self.expected_documents))
        object.__setattr__(self, "expected_citations", tuple(self.expected_citations))
        object.__setattr__(self, "extra", _frozen(self.extra))


@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidItem:
    """Item que não roda por problema de formato, nomeado no relatório."""

    id: str | None
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GoldenSet:
    """O conjunto dourado lido do arquivo (contracts/eval-harness.md)."""

    name: str
    items: Sequence[GoldenItem]
    assistant: str | None = None
    k: Sequence[int] = DEFAULT_K
    tolerances: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))
    invalid: Sequence[InvalidItem] = ()

    def __post_init__(self) -> None:
        _require_text("name", self.name)
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "invalid", tuple(self.invalid))
        object.__setattr__(self, "k", tuple(self.k))
        object.__setattr__(self, "tolerances", MappingProxyType(dict(self.tolerances)))
        if not self.k or any(isinstance(k, bool) or not isinstance(k, int) or k < 1 for k in self.k):
            raise ValueError(f"k precisa ser uma lista de inteiros >= 1: {list(self.k)!r}")
        negative = sorted(name for name, value in self.tolerances.items() if value < 0)
        if negative:
            raise ValueError(f"tolerância negativa em {', '.join(negative)}")
        seen: set[str] = set()
        for item in self.items:
            if item.id in seen:
                raise ValueError(f"id repetido no conjunto: {item.id}")
            seen.add(item.id)


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricValue:
    """Uma métrica agregada da rodada. `value` `None` = ausente (ex.: sem juiz); `n` = itens em que se aplicou."""

    name: str
    value: float | None
    n: int
    deterministic: bool
    better: Better | None
    variance: float | None = None

    def __post_init__(self) -> None:
        _require_text("name", self.name)
        if self.better is not None and self.better not in _BETTER:
            raise ValueError(f"better precisa ser 'higher', 'lower' ou None: {self.better!r}")


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemResult:
    """O que a rodada observou num item."""

    id: str
    metrics: Mapping[str, float | None] = field(default_factory=lambda: MappingProxyType({}))
    citations: Sequence[Mapping[str, JSONValue]] = ()
    flags: Sequence[str] = ()
    issue_kinds: Sequence[str] = ()
    gate_route: str | None = None
    failure: str | None = None
    warnings: Sequence[str] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))
        object.__setattr__(self, "citations", tuple(MappingProxyType(dict(c)) for c in self.citations))
        for name in ("flags", "issue_kinds", "warnings"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True, kw_only=True)
class EvalReport:
    """O relatório de uma rodada (formato de seam: a linha de base é um relatório)."""

    golden_set: str
    assistant: str
    started_at: datetime
    core_version: str
    k: Sequence[int]
    metrics: Sequence[MetricValue]
    items: Sequence[ItemResult] = ()
    invalid: Sequence[InvalidItem] = ()
    annotations: Sequence[str] = ()
    judge: str | None = None

    def __post_init__(self) -> None:
        for name in ("k", "metrics", "items", "invalid", "annotations"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    def metric(self, name: str) -> MetricValue | None:
        return next((metric for metric in self.metrics if metric.name == name), None)


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricDelta:
    """A comparação de uma métrica com a linha de base. Só determinísticas regridem."""

    name: str
    baseline: float | None
    current: float | None
    delta: float | None
    tolerance: float
    regressed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Comparison:
    """A rodada contra a linha de base; `missing` = métricas da base que a rodada não tem."""

    deltas: Sequence[MetricDelta]
    missing: Sequence[str] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "deltas", tuple(self.deltas))
        object.__setattr__(self, "missing", tuple(self.missing))

    @property
    def regressed(self) -> bool:
        return any(delta.regressed for delta in self.deltas)


class EvalHarness(Protocol):
    """Seam do harness: roda um conjunto dourado contra um Assistant e devolve o relatório."""

    async def run(
        self, golden: GoldenSet, *, assistant: str, principal: Principal, annotations: Sequence[str] = ()
    ) -> EvalReport:
        """Itens em sequência, pelo Execution Engine com a data de cada item. Levanta `EvalInputError` antes de
        rodar qualquer item quando o Assistant não resolve ou o trace não pode ser lido."""
        ...
