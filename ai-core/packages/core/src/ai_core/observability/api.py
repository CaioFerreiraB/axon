"""Seams da spec 009: Trace Sink (emissão) e Trace (consulta).

Contrato em specs/009-core-observability-evaluation/contracts/trace-api.md.

Único módulo da 009 que outros módulos importam. Depende só da stdlib e da API pública de `ai_core_contracts`: nenhum
tipo de biblioteca de observabilidade aparece aqui (FR-013, research R1). Acrescentar um tipo de evento é acrescentar
uma dataclass e um membro de `TraceEvent` — a assinatura de `emit` não muda.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ai_core_contracts import JSONValue


class TraceQueryUnavailable(RuntimeError):
    """O backend configurado não oferece consulta de trace (research R5)."""


def _require_text(field: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} não pode ser vazio")


def _require_aware(field: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} precisa ter timezone")


def _require_non_negative(field: str, value: float | None) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{field} não pode ser negativo")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionStarted:
    """Começo de uma execução.

    `reference_time` é a data de referência da execução (ADR-013), não o instante do evento.
    """

    request_id: str
    assistant: str
    flow: str
    packs: tuple[str, ...] = ()
    reference_time: datetime

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("assistant", self.assistant)
        _require_text("flow", self.flow)
        _require_aware("reference_time", self.reference_time)


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelCall:
    """Uma chamada de provider de modelo. `role` é texto: o vocabulário de papéis é da 006."""

    request_id: str
    role: str
    provider: str
    model: str
    duration_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("role", self.role)
        _require_text("provider", self.provider)
        _require_text("model", self.model)
        _require_non_negative("duration_ms", self.duration_ms)
        _require_non_negative("input_tokens", self.input_tokens)
        _require_non_negative("output_tokens", self.output_tokens)


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationRun:
    """Execução de um validator de pack."""

    request_id: str
    pack: str
    validator: str
    ok: bool
    issues: tuple[str, ...] = ()
    flags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("pack", self.pack)
        _require_text("validator", self.validator)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionError:
    """Erro durante a execução. `message` é texto livre — é redigido e truncado na serialização (FR-002)."""

    request_id: str
    stage: str
    kind: str
    message: str

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("stage", self.stage)
        _require_text("kind", self.kind)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionFinished:
    """Fim de uma execução. `reason` é livre: o vocabulário de desfechos é interno da 005 (research R2)."""

    request_id: str
    ok: bool
    duration_ms: float
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_non_negative("duration_ms", self.duration_ms)


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCall:
    """Uma chamada de tool pelo gateway (004 FR-014). Sem argumentos nem conteúdo: o trace não guarda dado de usuário;
    a auditoria guarda os de escrita. `kind` é `None` quando a tool não existe no catálogo."""

    request_id: str
    tool: str
    kind: str | None
    status: str
    duration_ms: float
    size_bytes: int
    truncated: bool = False

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("tool", self.tool)
        _require_text("status", self.status)
        _require_non_negative("duration_ms", self.duration_ms)
        _require_non_negative("size_bytes", self.size_bytes)


type TraceEvent = ExecutionStarted | ModelCall | ValidationRun | ToolCall | ExecutionError | ExecutionFinished
"""Dados de trace que os emissores mandam. Tipo novo entra aqui sem mudar o seam."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceRecord:
    """Um registro de trace, como o backend guarda e a consulta devolve (contracts/record-format.md)."""

    at: datetime
    type: str
    request_id: str
    attributes: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True, kw_only=True)
class Trace:
    """Os registros de uma requisição, na ordem de emissão."""

    request_id: str
    records: tuple[TraceRecord, ...] = ()


class TraceSink(Protocol):
    """Porta de emissão (ADR-013), consumida por 004, 005 e 006."""

    def emit(self, event: TraceEvent) -> None:
        """Registra um dado de trace. NUNCA levanta e NUNCA bloqueia perceptivelmente (FR-011)."""
        ...


class TraceQuery(Protocol):
    """Consulta de trace por requisição, consumida pela 008 e pelo operador."""

    def trace(self, request_id: str) -> Trace:
        """Eventos da requisição, em ordem. Levanta `TraceQueryUnavailable` se o backend não lê."""
        ...

    def dropped_events(self) -> int:
        """Eventos descartados por falha do backend desde o início do processo (FR-011)."""
        ...
