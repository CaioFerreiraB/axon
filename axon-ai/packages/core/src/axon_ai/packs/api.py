"""Seams da spec 002: Pack Registry e Pack Hooks (specs/002-core-pack-runtime/contracts/pack-runtime-api.md).

Único módulo da 002 que outros módulos importam. Depende só da stdlib e da API pública de `axon_ai_contracts`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

from axon_ai_contracts import (
    Citation,
    EvalMetric,
    JSONValue,
    NamedRetriever,
    Reranker,
    ToolSpec,
    TurnView,
    ValidationResult,
)

type Slices = Mapping[str, Mapping[str, JSONValue]]
"""Fatia de cada pack da composição, mantida pelo motor entre os passos de uma execução."""


class PackStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrieverCapability:
    name: str
    collections: frozenset[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class PackCapabilities:
    """O que um pack habilitado declarou, coletado uma vez na carga (001 FR-019)."""

    system_prompt: bool
    tools: tuple[str, ...]
    retrievers: tuple[RetrieverCapability, ...]
    reranker: bool
    validators: tuple[str, ...]
    preferred_flow: str | None
    depends_on: tuple[str, ...]
    requires_collections: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class PackEntry:
    """Estado de um pack instalado (ou citado na configuração) no Pack Registry (FR-006)."""

    name: str
    version: str | None
    contract_version: str | None
    origin: Literal["code", "declarative"]
    status: PackStatus
    error: str | None = None
    capabilities: PackCapabilities | None = None

    def __post_init__(self) -> None:
        if self.status is PackStatus.ERROR and not self.error:
            raise ValueError(f"pack {self.name!r} em erro precisa de mensagem de erro")


@dataclass(frozen=True, slots=True, kw_only=True)
class Composition:
    """Lista ordenada de packs de uma execução, validada por `PackRegistry.compose`. Não carrega instâncias."""

    packs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "packs", tuple(self.packs))


class CompositionError(ValueError):
    """A lista de packs não pode ser composta (pack indisponível, repetido ou dependência fora de ordem)."""

    def __init__(self, message: str, *, packs: Sequence[str]) -> None:
        super().__init__(message)
        self.packs = tuple(packs)


class PackHookError(RuntimeError):
    """Um hook de pack falhou ou devolveu valor fora do contrato durante uma execução (FR-011)."""

    def __init__(self, message: str, *, pack: str, hook: str) -> None:
        super().__init__(message)
        self.pack = pack
        self.hook = hook


class PackConfigError(ValueError):
    """Configuração de packs do operador malformada; a composition root para o boot."""


class PackRegistry(Protocol):
    def entries(self) -> Sequence[PackEntry]:
        """Uma entrada por pack instalado ou citado na configuração, ordenadas por nome."""
        ...

    def entry(self, name: str) -> PackEntry | None: ...

    def compose(self, pack_names: Sequence[str]) -> Composition:
        """Valida a lista ordenada de um Assistant; levanta `CompositionError`."""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatorRun:
    pack: str
    validator: str
    result: ValidationResult


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationOutcome:
    """Resultado dos validators da composição, em sequência, com resposta e citações encadeadas."""

    ok: bool
    answer: str | None
    citations: tuple[Citation, ...]
    flags: frozenset[str]
    runs: tuple[ValidatorRun, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamedValidation:
    """O que o filtro da geração entregou (ADR-024): a cauda a emitir depois do último pedaço, a resposta inteira já
    filtrada (o que saiu mais a cauda) e as execuções dos validators que filtraram, na ordem da sequência."""

    tail: str
    answer: str
    runs: tuple[ValidatorRun, ...] = ()


class AnswerFilter(Protocol):
    """Filtro da resposta em geração: encadeia as sessões `open_stream` dos validators do prefixo (ADR-024)."""

    def feed(self, delta: str) -> str:
        """O texto pronto para sair agora; pode segurar o que os validators ainda não decidiram."""
        ...

    def finish(self) -> StreamedValidation:
        """Fecha as sessões, em ordem; levanta `PackHookError` se um validator quebra a regra do contrato."""
        ...


class PackHooks(Protocol):
    def system_prompts(self, composition: Composition) -> tuple[str, ...]:
        """Fragmentos de instrução, na ordem da composição."""
        ...

    async def prepare(self, composition: Composition, view: TurnView, slices: Slices) -> Slices:
        """Preparação de contexto pack a pack; devolve as fatias novas da composição."""
        ...

    def open_answer_stream(self, composition: Composition, view: TurnView, slices: Slices) -> AnswerFilter:
        """Abre o filtro da geração com os validators de `open_stream` que formam o prefixo da sequência de validators
        da composição (ADR-024). Sem nenhum, o filtro deixa tudo passar."""
        ...

    async def validate(
        self, composition: Composition, view: TurnView, slices: Slices, streamed: StreamedValidation | None = None
    ) -> ValidationOutcome:
        """Validators em sequência, com resposta e citações encadeadas. Com `streamed`, as execuções do filtro valem
        pelos primeiros validators da sequência, e só os restantes rodam, sobre a resposta já filtrada (ADR-024)."""
        ...

    def reranker(self, composition: Composition, pack: str) -> Reranker | None:
        """O reranker que `pack` declarou, coletado na carga, ou `None` (Fase 5; 005 research R38).

        Por pack porque o reranker de um pack pode depender do que o retriever dele grava nos chunks; o motor reordena
        cada grupo com o reranker do próprio pack. Pack fora da composição → `ValueError` nomeando o pack.
        """
        ...


# --- Pack Toolset (Fase 3, US3 cenário 1; research R18, R19) — consumido pela 004 ------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class PackTool:
    """Uma tool de pack numa composição: nome com namespace (`<pack>.<nome>`, FR-007), o `ToolSpec` com o nome local e,
    em recuperação, o retriever com as coleções que declara."""

    name: str
    pack: str
    spec: ToolSpec
    retriever: NamedRetriever | None = None


class PackToolset(Protocol):
    def toolset(self, composition: Composition) -> Sequence[PackTool]:
        """Por pack, na ordem da composição revalidada: tools nativas na ordem declarada, depois os retrievers como
        tools de recuperação. Sem I/O: o catálogo foi coletado na carga."""
        ...


# --- Métricas de domínio (Fase 6; ADR-027) — consumido pelo harness da 009 -------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class PackEvalMetric:
    """Uma métrica de domínio de um pack da composição. O harness a reporta como `<pack>:<nome>`."""

    pack: str
    metric: EvalMetric


class PackEvalMetrics(Protocol):
    def eval_metrics(self, composition: Composition) -> Sequence[PackEvalMetric]:
        """As métricas que os packs da composição declararam pelo hook opcional `eval_metrics` (001, ADR-027), na
        ordem da composição. Coletadas na carga — nenhuma chamada a pack aqui. Composição revalidada."""
        ...


# --- Preparo de dados (ADR-041) — consumido pelo comando `packs prepare`, que a 011 registra --------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class PreparedPack:
    """O desfecho do preparo de um pack habilitado. `error` traz a causa, na forma que o comando imprime."""

    name: str
    data_dir: Path | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class PackDataPreparation(Protocol):
    def prepare_data(self) -> Sequence[PreparedPack]:
        """Para cada pack habilitado, em ordem de nome: leva o pack até a configuração validada (sem os hooks de
        catálogo), cria o diretório de dados e chama o hook `prepare` (001, ADR-041). Falha de um pack não impede os
        demais. Não carrega o registry. Levanta `PackConfigError` com a configuração malformada."""
        ...
