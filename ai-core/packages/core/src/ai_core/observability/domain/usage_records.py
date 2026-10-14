"""Registros do uso (ADR-034, research R30): o que o destino de uso grava e o que o armazenamento agrega. Sem texto
nenhum. Moram no domínio porque a projeção e a agregação os leem; `ports.py` os reexporta."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

type Origin = Literal["production", "evaluation"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelCallRow:
    """Uma chamada de modelo para o relatório de uso (R30): sem texto nenhum."""

    request_id: str
    at: datetime
    origin: Origin
    assistant: str | None
    provider: str
    model: str
    role: str
    input_tokens: int
    output_tokens: int
    duration_ms: float
    failed: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionRow:
    request_id: str
    started_at: datetime
    origin: Origin
    assistant: str
    flow: str
    finished_at: datetime | None = None
    ok: bool | None = None
    duration_ms: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DailyTokens:
    """Chamadas e tokens de um dia local, por chave (modelo ou Assistant) e modelo — o preço é por modelo."""

    day: date
    key: str | None
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DailyRequests:
    day: date
    key: str | None
    requests: int


@dataclass(frozen=True, slots=True, kw_only=True)
class KeyRequests:
    """Requisições distintas de uma chave no período inteiro (somar os dias contaria duas vezes a que vira a noite)."""

    key: str | None
    requests: int


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageAggregate:
    tokens: tuple[DailyTokens, ...] = ()
    requests: tuple[DailyRequests, ...] = ()
    key_requests: tuple[KeyRequests, ...] = ()
    total_requests: int = 0
