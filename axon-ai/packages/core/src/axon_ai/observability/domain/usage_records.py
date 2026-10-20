"""Registros do uso (ADR-034, research R30): o que o destino de uso grava e o que o armazenamento agrega. Sem texto
nenhum. Moram no domínio porque a projeção e a agregação os leem; `ports.py` os reexporta."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
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
    reported_cost: Decimal | None = None
    """O custo que o provider informou (ADR-035); `None` quando ele não informa."""


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
    """Chamadas e tokens de um dia local, por chave (modelo ou Assistant) e modelo — o preço é por modelo.

    Os campos `reported_*` são a parte das chamadas com custo informado pelo provider (ADR-035): o custo delas é a soma
    informada, e só o resto dos tokens passa pela tabela de preços.
    """

    day: date
    key: str | None
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    reported_calls: int = 0
    reported_input_tokens: int = 0
    reported_output_tokens: int = 0
    reported_cost: Decimal = Decimal(0)

    @property
    def unreported_input_tokens(self) -> int:
        return self.input_tokens - self.reported_input_tokens

    @property
    def unreported_output_tokens(self) -> int:
        return self.output_tokens - self.reported_output_tokens

    @property
    def needs_price(self) -> bool:
        """Sobram tokens sem custo informado. Chamada sem token nenhum (a que falhou) não pede preço."""
        return self.unreported_input_tokens > 0 or self.unreported_output_tokens > 0


@dataclass(frozen=True, slots=True, kw_only=True)
class DailyRequests:
    day: date
    key: str | None
    requests: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DayRequests:
    """Requisições distintas de um dia local, de qualquer chave (ADR-036)."""

    day: date
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
    day_requests: tuple[DayRequests, ...] = ()
    total_requests: int = 0
