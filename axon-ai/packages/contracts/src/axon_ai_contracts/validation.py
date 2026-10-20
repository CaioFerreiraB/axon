"""Validação determinística da resposta (FR-008, ADR-007). O contexto de validator nunca expõe modelos (FR-019)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from axon_ai_contracts._freeze import JSONValue, empty_mapping, freeze_mapping, freeze_sequence, require_non_empty
from axon_ai_contracts.view import Citation, TurnView


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatorContext:
    """Contexto de um validator: só dados de carga do pack. Tipo próprio para nunca herdar serviços do PackContext."""

    pack_name: str
    config: Mapping[str, JSONValue] = field(default_factory=empty_mapping)

    def __post_init__(self) -> None:
        require_non_empty("pack_name", self.pack_name)
        object.__setattr__(self, "config", freeze_mapping(self.config))


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationResult:
    """Resultado de um validator. `answer` e `citations` valem `None` quando o validator não os altera."""

    ok: bool
    issues: Sequence[str] = ()
    answer: str | None = None
    citations: Sequence[Citation] | None = None
    flags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", freeze_sequence(self.issues))
        if self.citations is not None:
            object.__setattr__(self, "citations", freeze_sequence(self.citations))
        object.__setattr__(self, "flags", frozenset(self.flags))


@runtime_checkable
class AnswerValidator(Protocol):
    """Checagem determinística da resposta: mesma entrada, mesmo resultado; sem acesso a modelos."""

    name: str

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult: ...


@runtime_checkable
class AnswerStream(Protocol):
    """Sessão de validação incremental de uma resposta em geração (ADR-024; contratos 0.1.1).

    `feed` recebe cada pedaço gerado e devolve o texto pronto para sair agora — pode segurar o que ainda não decidiu.
    `finish` fecha a sessão: o `answer` do resultado começa com a concatenação do que `feed` devolveu (o fim só
    acrescenta) — ou é `None`, quando nada muda e `feed` devolveu a resposta inteira — e o resultado é igual ao de
    `validate` sobre a resposta inteira, qualquer que seja a partição em pedaços.
    """

    def feed(self, delta: str) -> str: ...

    def finish(self) -> ValidationResult: ...


@runtime_checkable
class StreamingValidator(AnswerValidator, Protocol):
    """Validator que também filtra a resposta durante a geração (ADR-024; contratos 0.1.1).

    A sessão recebe a Turn View da abertura — antes da geração, sem `answer` — e não depende de citações de validators
    anteriores. Mesmas regras de `validate`: determinístico e sem acesso a modelos.
    """

    def open_stream(self, view: TurnView, ctx: ValidatorContext) -> AnswerStream: ...
