"""Seams da spec 002: Pack Registry e Pack Hooks (specs/002-core-pack-runtime/contracts/pack-runtime-api.md).

Único módulo da 002 que outros módulos importam. Depende só da stdlib e da API pública de `ai_core_contracts`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

from ai_core_contracts import Citation, JSONValue, NamedRetriever, ToolSpec, TurnView, ValidationResult

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


class PackHooks(Protocol):
    def system_prompts(self, composition: Composition) -> tuple[str, ...]:
        """Fragmentos de instrução, na ordem da composição."""
        ...

    async def prepare(self, composition: Composition, view: TurnView, slices: Slices) -> Slices:
        """Preparação de contexto pack a pack; devolve as fatias novas da composição."""
        ...

    async def validate(self, composition: Composition, view: TurnView, slices: Slices) -> ValidationOutcome:
        """Validators em sequência, com resposta e citações encadeadas."""
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
