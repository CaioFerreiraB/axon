"""Seam Execution Engine (spec 005): a única porta de entrada para executar.

Contrato em specs/005-core-execution-engine/contracts/execution-engine.md.

Único módulo da 005 que outros módulos importam. Depende só da stdlib, de `ai_core_contracts` e do `api.py` da 003 (o
grant). **Nenhum tipo de framework de grafo, de estado interno ou de HTTP aparece aqui** — é o que o ADR-011 e o SC-001
exigem: trocar o framework não pode mudar o que a 008 e o harness leem.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal, Protocol

from ai_core.assistants.api import ExecutionGrant
from ai_core.llm.api import ModelRole
from ai_core_contracts import Citation, Message

__all__ = [
    "FLOW_AGENTIC",
    "FLOW_CHAT",
    "ExecutionEngine",
    "ExecutionError",
    "ExecutionEvent",
    "ExecutionGrant",
    "ExecutionIssue",
    "ExecutionRequest",
    "ExecutionRequestInvalid",
    "FinalEvent",
    "IssueSeverity",
    "ProgressEvent",
    "TokenEvent",
    "UnknownFlow",
]

FLOW_CHAT: Final = "chat"
"""Conversa direta, sem tools e sem retrieval."""

FLOW_AGENTIC: Final = "agentic"
"""Loop do controller sobre o catálogo de tools da execução (US2, Fase 3). Só existe com o gateway da 004 ligado."""


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


# `ExecutionGrant` é o value object da 003, reexportado (ADR-018, research R15): o motor lê `assistant`, `flow`,
# `composition`, `models` e `limits`, e entrega o grant inteiro à 004 ao abrir a sessão de tools. Nas Fases 1 e 2 ele
# chegava por um `Protocol` publicado aqui — a ponte do R3, que terminou quando a 004 passou a exigir o tipo concreto.


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


type IssueSeverity = Literal["error", "notice"]
"""`error`: falha da execução ou de uma dependência. `notice`: registrado, mas não é falha — resultado de política
(limite, ação inválida, teto de contexto) ou apontamento de validator (ADR-018, research R23)."""

_SEVERITIES: Final = frozenset({"error", "notice"})


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionIssue:
    """Um registro da execução. `message` é texto livre — a 009 o redige antes de gravar. Quem consome decide sucesso
    por `severity`, nunca pelo `kind`."""

    stage: str
    kind: str
    message: str
    severity: IssueSeverity = "error"

    def __post_init__(self) -> None:
        _require_text("stage", self.stage)
        _require_text("kind", self.kind)
        if self.severity not in _SEVERITIES:
            raise ValueError(f"severity precisa ser 'error' ou 'notice': {self.severity!r}")


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

    def flow_roles(self) -> Mapping[str, tuple[ModelRole, ...]]:
        """Para cada flow de `flows()`, os papéis de modelo que uma execução dele resolve — os mesmos que `run` confere.

        Dado, como os nomes de flow: a 003 recusa, antes de servir, o Assistant que não declara um papel exigido pelo
        flow dele (ADR-019).
        """
        ...

    def run(self, grant: ExecutionGrant, request: ExecutionRequest) -> AsyncIterator[ExecutionEvent]:
        """Executa e devolve o fluxo de eventos.

        **Não** é gerador: valida requisição, flow e grant de forma síncrona e levanta `ExecutionRequestInvalid` ou
        `UnknownFlow` na própria chamada, para que a 008 responda 4xx sem abrir o stream e sem custo (research R5).
        Depois do primeiro evento nada levanta: falha vira `FinalEvent` com erros (research R6). O grant é o da 003
        (ADR-018).
        """
        ...
