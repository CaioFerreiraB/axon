"""Seam Execution Engine (spec 005): a única porta de entrada para executar.

Contrato em specs/005-core-execution-engine/contracts/execution-engine.md.

Único módulo da 005 que outros módulos importam. Depende só da stdlib, de `ai_core_contracts` e dos `api.py` de 002 e
006. **Nenhum tipo de framework de grafo, de estado interno ou de HTTP aparece aqui** — é o que o ADR-011 e o SC-001
exigem: trocar o framework não pode mudar o que a 008 e o harness leem.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Protocol

from ai_core.llm.api import ModelPolicy
from ai_core.packs.api import Composition
from ai_core_contracts import Citation, Message

FLOW_CHAT: Final = "chat"
"""Conversa direta, sem tools e sem retrieval. Os outros nomes (`agentic`, `rag_first`) chegam nas fases deles."""


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} não pode ser vazio")


class ExecutionError(RuntimeError):
    """Base dos erros do motor. Só acontecem **antes** do primeiro evento; depois dele, falha vira `FinalEvent`."""


class ExecutionRequestInvalid(ExecutionError):
    """A requisição não pode ser executada (FR-013). Levantada na chamada de `run`, antes de qualquer custo."""


class UnknownFlow(ExecutionRequestInvalid):
    """O flow do grant não está no registro (US5 cenário 2)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionRequest:
    """O que se pede ao motor. `reference_time` só é preenchida pelo harness em processo (ADR-013, 008 FR-012)."""

    request_id: str
    messages: Sequence[Message]
    stream: bool = True
    reference_time: datetime | None = None

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        if not self.messages:
            raise ValueError("a requisição precisa de ao menos uma mensagem")
        if self.reference_time is not None and (
            self.reference_time.tzinfo is None or self.reference_time.utcoffset() is None
        ):
            raise ValueError("reference_time precisa ter timezone")
        object.__setattr__(self, "messages", tuple(self.messages))


class ExecutionGrant(Protocol):
    """A forma que o motor exige do Execution Grant.

    O valor é produzido pela 003 a partir da Fase 2 e pela composition root (011) na Fase 1; qualquer objeto com estes
    quatro atributos serve, o que mantém a direção `005 → 003` do grafo de dependências sem import nenhum
    (research R3). Cresce de forma aditiva: limites de iteração na Fase 3, teto de contexto na Fase 5.
    """

    @property
    def assistant(self) -> str:
        """Nome do Assistant resolvido."""
        ...

    @property
    def flow(self) -> str:
        """Nome do flow a executar."""
        ...

    @property
    def composition(self) -> Composition:
        """Packs da execução, já compostos e validados pela 002."""
        ...

    @property
    def models(self) -> ModelPolicy:
        """Modelo por papel e allowlist (006)."""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenEvent:
    """Um pedaço da resposta, na ordem em que o modelo o produziu."""

    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProgressEvent:
    """Uma etapa começou. O progresso de `generate` é o primeiro sinal barato que a SC-004 mede."""

    stage: str
    detail: str | None = None

    def __post_init__(self) -> None:
        _require_text("stage", self.stage)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionIssue:
    """Um problema registrado na execução. `message` é texto livre — a 009 o redige antes de gravar."""

    stage: str
    kind: str
    message: str

    def __post_init__(self) -> None:
        _require_text("stage", self.stage)
        _require_text("kind", self.kind)


@dataclass(frozen=True, slots=True, kw_only=True)
class FinalEvent:
    """Fecha toda execução, inclusive a que falhou no meio: resposta (possivelmente parcial), citações e erros."""

    answer: str
    citations: tuple[Citation, ...] = ()
    errors: tuple[ExecutionIssue, ...] = ()
    flags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "flags", frozenset(self.flags))


type ExecutionEvent = TokenEvent | ProgressEvent | FinalEvent
"""O que o consumidor recebe. Toda execução termina com exatamente um `FinalEvent`, sempre o último."""


class ExecutionEngine(Protocol):
    """Seam da 005, consumido por 008 (traduz em SSE), 003 (valida nomes) e pelo harness da 009."""

    def flows(self) -> frozenset[str]:
        """Nomes de flow disponíveis. Dado, não código: `assistants validate` (003) os usa."""
        ...

    def run(self, grant: ExecutionGrant, request: ExecutionRequest) -> AsyncIterator[ExecutionEvent]:
        """Executa e devolve o fluxo de eventos.

        **Não** é gerador: valida requisição, flow e grant de forma síncrona e levanta `ExecutionRequestInvalid` ou
        `UnknownFlow` na própria chamada, para que a 008 responda 4xx sem abrir o stream e sem custo (research R5).
        Depois do primeiro evento nada levanta: falha vira `FinalEvent` com erros (research R6).
        """
        ...
