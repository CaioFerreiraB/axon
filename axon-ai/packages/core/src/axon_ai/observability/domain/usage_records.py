"""Registros do uso (ADR-034, research R30): o que o destino de uso grava e o que o armazenamento agrega. Sem texto
nenhum. Moram no domínio porque a projeção e a agregação os leem; `ports.py` os reexporta."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal

type Origin = Literal["production", "evaluation"]

IMPACT_METRICS: Final = (
    "energy_kwh",
    "gwp_kgco2eq",
    "adpe_kgsbeq",
    "pe_mj",
    "wcf_l",
    "gwp_usage",
    "gwp_embodied",
    "adpe_usage",
    "adpe_embodied",
    "pe_usage",
    "pe_embodied",
)
"""As grandezas do EcoLogits que a linha guarda (ADR-056, item 4): as cinco do total e GWP, ADPe e PE por fase."""

IMPACT_COLUMNS: Final = tuple(f"{metric}_{end}" for metric in IMPACT_METRICS for end in ("min", "max"))
"""As 22 colunas `double precision` da migração `005_impacts.sql`, na ordem dela."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ImpactEstimate:
    """O impacto de uma chamada (research R44): os extremos de cada grandeza, com a impressão digital da estimativa."""

    model: str
    """`provedor/nome` do modelo do EcoLogits usado."""
    match: Literal["exact", "approximate"]
    zone: str
    version: str
    values: Mapping[str, float]
    """Uma entrada por nome de `IMPACT_COLUMNS`."""
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        missing = set(IMPACT_COLUMNS) - set(self.values)
        if missing:
            raise ValueError(f"estimativa sem {sorted(missing)}")


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
    impact: ImpactEstimate | None = None
    impact_tried: bool = False
    """Estimativa tentada (R46): com `impact` nulo, o modelo não tem par na base (`impact_match = 'none'`)."""


def eligible(row: ModelCallRow) -> bool:
    """Só a chamada que terminou e gerou tokens tem o que estimar."""
    return not row.failed and row.output_tokens > 0


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


@dataclass(frozen=True, slots=True, kw_only=True)
class ImpactCell:
    """Impacto de uma chave num balde (research R49): contagens e a soma de cada coluna das chamadas estimadas."""

    bucket: date
    key: str | None
    calls: int = 0
    eligible: int = 0
    estimated: int = 0
    approximate: int = 0
    estimated_output_tokens: int = 0
    sums: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImpactAggregate:
    """O que o armazenamento devolve para o relatório. Respostas são pares (todas, com alguma chamada estimada)."""

    cells: tuple[ImpactCell, ...] = ()
    bucket_responses: Mapping[date, tuple[int, int]] = field(default_factory=dict)
    key_responses: Mapping[str | None, tuple[int, int]] = field(default_factory=dict)
    key_models: Mapping[str | None, tuple[str, str]] = field(default_factory=dict)
    """Por chave, o modelo do EcoLogits e o casamento da chamada estimada mais recente."""
    responses: tuple[int, int] = (0, 0)


@dataclass(frozen=True, slots=True, kw_only=True)
class UnestimatedCall:
    """Uma chamada guardada que nunca foi estimada (research R50)."""

    id: int
    provider: str
    model: str
    output_tokens: int
    duration_ms: float
