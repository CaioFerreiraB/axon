"""Seam Execution Engine (spec 005): a única porta de entrada para executar.

Contrato em specs/005-core-execution-engine/contracts/execution-engine.md.

Único módulo da 005 que outros módulos importam. Depende só da stdlib, de `axon_ai_contracts` e do `api.py` da 003 (o
grant). **Nenhum tipo de framework de grafo, de estado interno ou de HTTP aparece aqui** — é o que o ADR-011 e o SC-001
exigem: trocar o framework não pode mudar o que a 008 e o harness leem.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Final, Literal, Protocol

from ai_core.assistants.api import ExecutionGrant
from ai_core.llm.api import ModelRole
from axon_ai_contracts import Citation, JSONValue, Message

__all__ = [
    "FLOW_AGENTIC",
    "FLOW_CHAT",
    "FLOW_RAG_FIRST",
    "CatalogOutcome",
    "ControllerAction",
    "ControllerOutcome",
    "ExecutionEngine",
    "ExecutionError",
    "ExecutionEvent",
    "ExecutionGrant",
    "ExecutionIssue",
    "ExecutionRequest",
    "ExecutionRequestInvalid",
    "FinalEvent",
    "GateOutcome",
    "GateRoute",
    "GenerationOutcome",
    "IssueSeverity",
    "ProgressEvent",
    "RagSettings",
    "RerankOutcome",
    "SourceRef",
    "StepFinished",
    "StepOutcome",
    "TokenEvent",
    "ToolCallSummary",
    "ToolCallsOutcome",
    "UnknownFlow",
]

FLOW_CHAT: Final = "chat"
"""Conversa direta, sem tools e sem retrieval."""

FLOW_AGENTIC: Final = "agentic"
"""Loop do controller sobre o catálogo de tools da execução (US2, Fase 3). Só existe com o gateway da 004 ligado."""

FLOW_RAG_FIRST: Final = "rag_first"
"""Recuperação e rerank determinísticos, portão de cobertura e uma chamada de modelo no caminho coberto (US3, Fase 5).
Como o `agentic`, só existe com o gateway da 004: a recuperação passa por ele (ADR-005)."""


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} não pode ser vazio")


def _require_count(field_name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} precisa ser um inteiro ≥ 1: {value!r}")


def _require_size(field_name: str, value: int | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError(f"{field_name} precisa ser um inteiro ≥ 0: {value!r}")


def _frozen(arguments: Mapping[str, JSONValue]) -> Mapping[str, JSONValue]:
    return MappingProxyType(dict(arguments))


@dataclass(frozen=True, slots=True, kw_only=True)
class RagSettings:
    """Os números do `rag_first`, do operador (`AI_CORE_RAG_*`, pela 011; FR-007, clarificação 1 de 2026-10-09).

    `candidates` vai como `top_k` a cada tool de recuperação; `passages` é quantos trechos o rerank leva à geração; e
    `min_score` é o limiar do portão sobre o melhor score dos trechos. **Sem limiar por default**: até a 105 calibrar,
    só a ausência de resultado escala (princípio X) — nenhum número é fixado no código.
    """

    candidates: int = 20
    passages: int = 5
    min_score: float | None = None

    def __post_init__(self) -> None:
        _require_count("candidates", self.candidates)
        _require_count("passages", self.passages)
        if self.min_score is not None and not 0.0 <= self.min_score <= 1.0:  # NaN também cai aqui
            raise ValueError(f"min_score precisa estar em [0, 1]: {self.min_score!r}")


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


# --- Desfecho de etapa (ADR-028) -----------------------------------------------------------------------------
# O que cada etapa fez, para quem acompanha a execução: chamadas, contagens, fontes e decisões. Nunca texto de trecho,
# conteúdo de resultado de tool, texto de erro de tool, prompt ou resposta. Os argumentos de tool podem ir: o stream é
# do próprio Principal (o trace, que o operador lê, continua sem eles — ADR-017).


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceRef:
    """Onde está um trecho — documento, seção e página —, nunca o texto."""

    document: str
    section: str | None = None
    page: int | None = None

    def __post_init__(self) -> None:
        _require_text("document", self.document)


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallSummary:
    """Uma chamada de tool da etapa: o que se pediu e o que voltou, sem o conteúdo nem o texto de erro.

    `kind` é o tipo do catálogo (`retrieval`…), `None` para tool fora dele; `status` é o do gateway da 004 (`ok`,
    `error`, `timeout`, `unknown`, `invalid_arguments`); `sources`, as fontes dos trechos que voltaram, na ordem.
    """

    tool: str
    kind: str | None = None
    arguments: Mapping[str, JSONValue] = field(default_factory=dict)
    status: str
    truncated: bool = False
    sources: tuple[SourceRef, ...] = ()

    def __post_init__(self) -> None:
        _require_text("tool", self.tool)
        _require_text("status", self.status)
        object.__setattr__(self, "arguments", _frozen(self.arguments))
        object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallsOutcome:
    """`retrieve` e `execute_tool`: as chamadas, na ordem. No `retrieve` que falha, até a que falhou."""

    calls: tuple[ToolCallSummary, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "calls", tuple(self.calls))


@dataclass(frozen=True, slots=True, kw_only=True)
class RerankOutcome:
    """`rerank`: de quantos candidatos, quais fontes ficaram (na ordem) e os packs cujo reranker falhou."""

    candidates: int
    kept: tuple[SourceRef, ...] = ()
    degraded: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_size("candidates", self.candidates)
        object.__setattr__(self, "kept", tuple(self.kept))
        object.__setattr__(self, "degraded", tuple(self.degraded))


type GateRoute = Literal["generate", "controller", "fallback"]
"""`generate`: gerar com os trechos; `controller`: escalar para o loop; `fallback`: gerar sem trechos."""

_GATE_ROUTES: Final = frozenset({"generate", "controller", "fallback"})


@dataclass(frozen=True, slots=True, kw_only=True)
class GateOutcome:
    """`gate`: a decisão do portão de cobertura e quantos trechos entraram no contexto da geração."""

    covered: bool
    route: GateRoute
    best_score: float | None = None
    threshold: float | None = None
    delivered: int = 0

    def __post_init__(self) -> None:
        if self.route not in _GATE_ROUTES:
            raise ValueError(f"rota do portão desconhecida: {self.route!r}")
        _require_size("delivered", self.delivered)


type ControllerAction = Literal["tool", "answer", "invalid", "failed"]
"""O que saiu de uma chamada ao controller. Os limites (iterações, contexto) não chamam o controller: são registros."""

_CONTROLLER_ACTIONS: Final = frozenset({"tool", "answer", "invalid", "failed"})


@dataclass(frozen=True, slots=True, kw_only=True)
class ControllerOutcome:
    """`controller`: a ação de uma iteração e o modelo que a decidiu. `reason` é curto e escrito pelo motor."""

    iteration: int
    action: ControllerAction
    model: str
    tool: str | None = None
    arguments: Mapping[str, JSONValue] | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_count("iteration", self.iteration)
        if self.action not in _CONTROLLER_ACTIONS:
            raise ValueError(f"ação do controller desconhecida: {self.action!r}")
        _require_text("model", self.model)
        if self.arguments is not None:
            object.__setattr__(self, "arguments", _frozen(self.arguments))


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerationOutcome:
    """`generate`: o modelo e os tokens, quando o provider os informa."""

    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        _require_text("model", self.model)
        _require_size("input_tokens", self.input_tokens)
        _require_size("output_tokens", self.output_tokens)


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogOutcome:
    """`load_capabilities`: quantas tools o catálogo da execução tem e os aliases MCP indisponíveis, sem o motivo."""

    tools: int
    unavailable: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_size("tools", self.tools)
        object.__setattr__(self, "unavailable", tuple(self.unavailable))


type StepOutcome = (
    ToolCallsOutcome | RerankOutcome | GateOutcome | ControllerOutcome | GenerationOutcome | CatalogOutcome
)


@dataclass(frozen=True, slots=True, kw_only=True)
class StepFinished:
    """Uma etapa terminou, depois de todos os eventos dela (ADR-028). `outcome` é `None` quando não há o que contar
    (`prepare_context`, `validate_answer`). O motor não mede tempo: quem consome mede do `ProgressEvent` até aqui."""

    stage: str
    outcome: StepOutcome | None = None

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


type ExecutionEvent = TokenEvent | ProgressEvent | StepFinished | FinalEvent
"""O que o consumidor recebe. Toda execução termina com exatamente um `FinalEvent`, sempre o último. Quem não precisa do
desfecho das etapas ignora o `StepFinished` (ADR-028)."""


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
