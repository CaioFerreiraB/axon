"""Fábricas dos testes de trace (spec 009, T004): instante fixo, eventos válidos e um exporter que falha."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from ai_core.observability.api import (
    ExchangeMessage,
    ExecutionError,
    ExecutionFinished,
    ExecutionStarted,
    ModelCall,
    ModelExchange,
    TraceRecord,
    ValidationRun,
)

AT: Final = datetime(2026, 9, 17, 14, tzinfo=UTC)
"""Instante do relógio fixo dos testes."""

REFERENCE_TIME: Final = datetime(2026, 9, 17, tzinfo=UTC)
"""Data de referência da execução (ADR-013)."""

REQUEST_ID: Final = "req-7f3a"


def started(request_id: str = REQUEST_ID, **overrides: object) -> ExecutionStarted:
    fields: dict[str, object] = {
        "request_id": request_id,
        "assistant": "geral",
        "flow": "chat",
        "packs": ("generic",),
        "reference_time": REFERENCE_TIME,
    }
    return ExecutionStarted(**(fields | overrides))  # type: ignore[arg-type]


def model_call(request_id: str = REQUEST_ID, **overrides: object) -> ModelCall:
    fields: dict[str, object] = {
        "request_id": request_id,
        "role": "generation",
        "provider": "ollama",
        "model": "qwen3:1.7b",
        "duration_ms": 8321.5,
        "input_tokens": 412,
        "output_tokens": 87,
    }
    return ModelCall(**(fields | overrides))  # type: ignore[arg-type]


def validation(request_id: str = REQUEST_ID, **overrides: object) -> ValidationRun:
    fields: dict[str, object] = {
        "request_id": request_id,
        "pack": "generic",
        "validator": "non_empty_answer",
        "ok": True,
    }
    return ValidationRun(**(fields | overrides))  # type: ignore[arg-type]


def failure(request_id: str = REQUEST_ID, **overrides: object) -> ExecutionError:
    fields: dict[str, object] = {
        "request_id": request_id,
        "stage": "generation",
        "kind": "ProviderTimeout",
        "message": "timeout após 30s",
    }
    return ExecutionError(**(fields | overrides))  # type: ignore[arg-type]


def finished(request_id: str = REQUEST_ID, **overrides: object) -> ExecutionFinished:
    fields: dict[str, object] = {"request_id": request_id, "ok": True, "duration_ms": 9102.7}
    return ExecutionFinished(**(fields | overrides))  # type: ignore[arg-type]


def record(request_id: str = REQUEST_ID, *, at: datetime = AT, **attributes: object) -> TraceRecord:
    """Registro pronto, para os testes das portas (que não passam pelo serviço)."""
    return TraceRecord(at=at, type="execution_finished", request_id=request_id, attributes=dict(attributes))  # type: ignore[arg-type]


class FailingTraceExporter:
    """Exporter que sempre falha: prova que a emissão não propaga (FR-011)."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error or OSError("disco cheio")
        self.attempts = 0

    def export(self, record: TraceRecord) -> None:
        self.attempts += 1
        raise self.error


# --- Fase 9 (ADR-034) -------------------------------------------------------------------------------------------------

MASTER_KEY: Final = bytes(range(32))


class MovingClock:
    """Relógio ajustável: o uso conta por dia local, e a saúde olha as últimas 24 h."""

    def __init__(self, instant: datetime = AT) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant

    def set(self, instant: datetime) -> None:
        self._instant = instant


def exchange(request_id: str = REQUEST_ID, **overrides: object) -> ModelExchange:
    fields: dict[str, object] = {
        "request_id": request_id,
        "role": "generation",
        "provider": "ollama",
        "model": "qwen3:1.7b",
        "messages": (
            ExchangeMessage(role="system", content="Você é útil."),
            ExchangeMessage(role="user", content="Minha chave é api_key=sk-segredo-123; qual é a capital?"),
        ),
        "output": "Brasília.",
    }
    return ModelExchange(**(fields | overrides))  # type: ignore[arg-type]
