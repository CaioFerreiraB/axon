"""Projeção de uso e o relatório de custo (ADR-034, research R30, R31). Puro: sem relógio nem armazenamento.

Do trace saem duas linhas, sem texto nenhum: a chamada de modelo (com o Assistant da execução, achado pelo
`request_id`) e a execução. O relatório agrega por dia **local** no fuso pedido — 23h30 em São Paulo conta no dia
local, não no UTC — e calcula o custo por modelo e dia: o que o provider informou vale como veio (ADR-035), e só os
tokens das chamadas sem custo informado passam pelo preço vigente naquele dia.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ai_core.observability.api import (
    InvalidQuery,
    Price,
    TraceRecord,
    UsageDay,
    UsageGrouping,
    UsageOrigin,
    UsageQuery,
    UsageReport,
    UsageRow,
)
from ai_core.observability.domain.prices import QUANTUM, cost, effective_price
from ai_core.observability.domain.usage_records import (
    DailyRequests,
    DailyTokens,
    DayRequests,
    ExecutionRow,
    KeyRequests,
    ModelCallRow,
    Origin,
    UsageAggregate,
)

EXECUTION_TTL: Final = timedelta(hours=1)
"""Por quanto tempo uma execução aberta espera as chamadas dela; depois, chamadas tardias ficam sem Assistant."""


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise InvalidQuery(f"fuso desconhecido: {name!r}", field="tz") from None


def window(query: UsageQuery) -> tuple[datetime, datetime]:
    """O período em instantes UTC: da meia-noite local do início à meia-noite local depois do fim."""
    tz = zone(query.tz)
    start = datetime.combine(query.start, time(), tzinfo=tz)
    end = datetime.combine(query.end + timedelta(days=1), time(), tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def previous(query: UsageQuery) -> UsageQuery:
    """O período de mesmo tamanho imediatamente antes — a comparação da faixa de números."""
    days = timedelta(days=query.days)
    return dataclasses.replace(query, start=query.start - days, end=query.end - days)


def local_day(at: datetime, tz: str) -> date:
    return at.astimezone(zone(tz)).date()


# --- projeção (o destino de uso) --------------------------------------------------------------------------------------


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _float(value: object) -> float:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def _cost(value: object) -> Decimal | None:
    """O custo informado, em `Decimal` pelo texto do número (sem herdar o ruído binário do `float`)."""
    if not isinstance(value, int | float) or isinstance(value, bool) or not value >= 0:
        return None
    return Decimal(str(value))


def execution_started(record: TraceRecord, *, origin: Origin) -> ExecutionRow:
    attributes = record.attributes
    return ExecutionRow(
        request_id=record.request_id,
        started_at=record.at,
        origin=origin,
        assistant=str(attributes.get("assistant", "")),
        flow=str(attributes.get("flow", "")),
    )


def execution_finished(row: ExecutionRow, record: TraceRecord) -> ExecutionRow:
    return dataclasses.replace(
        row,
        finished_at=record.at,
        ok=bool(record.attributes.get("ok")),
        duration_ms=_float(record.attributes.get("duration_ms")),
    )


def call_row(record: TraceRecord, *, assistant: str | None, origin: Origin) -> ModelCallRow:
    attributes = record.attributes
    return ModelCallRow(
        request_id=record.request_id,
        at=record.at,
        origin=origin,
        assistant=assistant,
        provider=str(attributes.get("provider", "")),
        model=str(attributes.get("model", "")),
        role=str(attributes.get("role", "")),
        input_tokens=_int(attributes.get("input_tokens")),
        output_tokens=_int(attributes.get("output_tokens")),
        duration_ms=_float(attributes.get("duration_ms")),
        failed=attributes.get("finish_reason") == "error",
        reported_cost=_cost(attributes.get("cost_usd")),
    )


# --- agregação (a mesma regra do SQL, para o armazenamento em memória) ------------------------------------------------


def key_of(row: ModelCallRow, by: UsageGrouping) -> str | None:
    return f"{row.provider}/{row.model}" if by == "model" else row.assistant


def aggregate(
    calls: Iterable[ModelCallRow],
    *,
    start: datetime,
    end: datetime,
    tz: str,
    by: UsageGrouping,
    origin: UsageOrigin,
) -> UsageAggregate:
    tokens: dict[tuple[date, str | None, str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    reported: dict[tuple[date, str | None, str, str], Decimal] = defaultdict(Decimal)
    daily_requests: dict[tuple[date, str | None], set[str]] = defaultdict(set)
    key_requests: dict[str | None, set[str]] = defaultdict(set)
    day_requests: dict[date, set[str]] = defaultdict(set)
    total: set[str] = set()
    for row in calls:
        if not start <= row.at < end or (origin != "all" and row.origin != origin):
            continue
        day, key = local_day(row.at, tz), key_of(row, by)
        group = (day, key, row.provider, row.model)
        counts = tokens[group]
        counts[0] += 1
        counts[1] += row.input_tokens
        counts[2] += row.output_tokens
        if row.reported_cost is not None:
            counts[3] += 1
            counts[4] += row.input_tokens
            counts[5] += row.output_tokens
            reported[group] += row.reported_cost
        daily_requests[(day, key)].add(row.request_id)
        key_requests[key].add(row.request_id)
        day_requests[day].add(row.request_id)
        total.add(row.request_id)
    return UsageAggregate(
        tokens=tuple(
            DailyTokens(
                day=day,
                key=key,
                provider=provider,
                model=model,
                calls=c[0],
                input_tokens=c[1],
                output_tokens=c[2],
                reported_calls=c[3],
                reported_input_tokens=c[4],
                reported_output_tokens=c[5],
                reported_cost=reported[(day, key, provider, model)],
            )
            for (day, key, provider, model), c in sorted(tokens.items(), key=lambda item: _sort_key(item[0]))
        ),
        requests=tuple(
            DailyRequests(day=day, key=key, requests=len(ids))
            for (day, key), ids in sorted(daily_requests.items(), key=lambda item: (item[0][0], item[0][1] or ""))
        ),
        key_requests=tuple(
            KeyRequests(key=key, requests=len(ids))
            for key, ids in sorted(key_requests.items(), key=lambda i: i[0] or "")
        ),
        day_requests=tuple(DayRequests(day=day, requests=len(ids)) for day, ids in sorted(day_requests.items())),
        total_requests=len(total),
    )


def _sort_key(key: tuple[date, str | None, str, str]) -> tuple[date, str, str, str]:
    day, group, provider, model = key
    return day, group or "", provider, model


# --- relatório --------------------------------------------------------------------------------------------------------


class _Totals:
    def __init__(self) -> None:
        self.calls = self.input_tokens = self.output_tokens = 0
        self.cost = Decimal(0)
        self.any_priced = False
        self.all_priced = True

    def add(self, item: DailyTokens, price: Price | None) -> None:
        self.calls += item.calls
        self.input_tokens += item.input_tokens
        self.output_tokens += item.output_tokens
        part, complete = group_cost(item, price)
        self.all_priced = self.all_priced and complete
        if part is not None:
            self.any_priced = True
            self.cost += part

    def row(self, key: str | None, requests: int) -> UsageRow:
        return UsageRow(
            key=key,
            calls=self.calls,
            requests=requests,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost=self.cost if self.any_priced else None,
            priced=self.all_priced,
        )


def group_cost(item: DailyTokens, price: Price | None) -> tuple[Decimal | None, bool]:
    """Custo de um grupo (dia, chave, modelo) e se ficou completo: o informado pelo provider mais, pela tabela, os
    tokens das chamadas sem custo informado (ADR-035). Sem preço vigente para esses tokens, o custo é só o informado —
    `None` se nenhuma chamada informou — e fica incompleto."""
    reported = item.reported_cost.quantize(QUANTUM) if item.reported_calls else None
    if not item.needs_price:
        return reported if reported is not None else Decimal(0).quantize(QUANTUM), True
    if price is None:
        return reported, False
    table = cost(price, input_tokens=item.unreported_input_tokens, output_tokens=item.unreported_output_tokens)
    return (item.reported_cost + table).quantize(QUANTUM), True


def period_cost(aggregate_: UsageAggregate, prices: Sequence[Price]) -> tuple[Decimal | None, bool]:
    """Custo do período (só as partes com preço) e se ficou incompleto."""
    totals = _Totals()
    for item in aggregate_.tokens:
        totals.add(item, effective_price(prices, provider=item.provider, model=item.model, day=item.day))
    if not aggregate_.tokens:
        return Decimal(0), False
    return (totals.cost if totals.any_priced else None), not totals.all_priced


def build_report(
    query: UsageQuery,
    aggregate_: UsageAggregate,
    prices: Sequence[Price],
    *,
    previous_cost: Decimal | None = None,
) -> UsageReport:
    by_day: dict[date, dict[str | None, _Totals]] = defaultdict(dict)
    by_key: dict[str | None, _Totals] = {}
    for item in aggregate_.tokens:
        price = effective_price(prices, provider=item.provider, model=item.model, day=item.day)
        by_day[item.day].setdefault(item.key, _Totals()).add(item, price)
        by_key.setdefault(item.key, _Totals()).add(item, price)
    daily_requests: Mapping[tuple[date, str | None], int] = {
        (entry.day, entry.key): entry.requests for entry in aggregate_.requests
    }
    key_requests: Mapping[str | None, int] = {entry.key: entry.requests for entry in aggregate_.key_requests}
    day_requests: Mapping[date, int] = {entry.day: entry.requests for entry in aggregate_.day_requests}
    days = tuple(
        UsageDay(
            day=day,
            rows=tuple(
                totals.row(key, daily_requests.get((day, key), 0))
                for key, totals in sorted(by_day[day].items(), key=lambda item: item[0] or "")
            ),
            requests=day_requests.get(day, 0),
        )
        for day in sorted(by_day)
    )
    totals = tuple(
        sorted(
            (totals.row(key, key_requests.get(key, 0)) for key, totals in by_key.items()),
            key=lambda row: (-(row.cost or Decimal(0)), -row.calls, row.key or ""),
        )
    )
    total_cost, incomplete = period_cost(aggregate_, prices)
    return UsageReport(
        query=query,
        days=days,
        totals=totals,
        total_cost=total_cost,
        requests=aggregate_.total_requests,
        incomplete=incomplete,
        previous_total_cost=previous_cost,
    )


def unpriced(aggregate_: UsageAggregate, prices: Sequence[Price]) -> tuple[str, ...]:
    """Modelos usados sem preço vigente em algum dia do agregado, quando sobram tokens sem custo informado."""
    missing = {
        f"{item.provider}/{item.model}"
        for item in aggregate_.tokens
        if item.needs_price and effective_price(prices, provider=item.provider, model=item.model, day=item.day) is None
    }
    return tuple(sorted(missing))
