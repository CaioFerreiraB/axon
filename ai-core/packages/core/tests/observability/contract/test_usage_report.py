"""T060 — `UsageReportSeam` e `PriceBook` (memória e Postgres): o relatório soma o que foi emitido (SC-005), o preço
lançado depois recalcula, sem preço fica incompleto."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from conftest import Stores
from trace_testkit import MovingClock, finished, model_call, started

from ai_core.observability.adapters.memory import FixedClock, InMemoryTraceBackend
from ai_core.observability.adapters.usage import UsageDestination
from ai_core.observability.api import InvalidPrice, UsageQuery
from ai_core.observability.service import TraceService, UsageService

pytestmark = pytest.mark.us5

DAY = datetime(2026, 10, 10, 15, tzinfo=UTC)


async def _emit(stores: Stores, *, at: datetime, request_id: str, origin: str = "production", **call: object) -> None:
    destination = UsageDestination(store=stores.usage, origin=origin, clock=FixedClock(at))  # type: ignore[arg-type]
    primary = InMemoryTraceBackend()
    trace = TraceService(exporter=primary, reader=primary, clock=FixedClock(at), destinations=(destination,))
    trace.emit(started(request_id=request_id, assistant="geral"))
    trace.emit(model_call(request_id=request_id, provider="openrouter", model="a", **call))
    trace.emit(finished(request_id=request_id))
    await trace.flush()


async def test_relatorio_soma_o_emitido_e_o_preco_recalcula(stores: Stores) -> None:
    clock = MovingClock(DAY)
    usage = UsageService(store=stores.usage, prices=stores.prices, clock=clock, default_timezone="America/Sao_Paulo")
    await _emit(stores, at=DAY, request_id="r1", input_tokens=1_000_000, output_tokens=0)
    await _emit(stores, at=DAY + timedelta(days=1), request_id="r2", input_tokens=500_000, output_tokens=100_000)
    await _emit(stores, at=DAY, request_id="e1", origin="evaluation", input_tokens=9, output_tokens=9)
    query = UsageQuery(start=date(2026, 10, 10), end=date(2026, 10, 11), tz="America/Sao_Paulo")
    report = await usage.report(query)
    (row,) = report.totals
    assert (row.key, row.calls, row.requests, row.input_tokens, row.output_tokens) == (
        "openrouter/a",
        2,
        2,
        1_500_000,
        100_000,
    )
    assert report.total_cost is None and report.incomplete and not row.priced  # sem preço ainda
    assert await usage.unpriced_models(start=date(2026, 10, 10), end=date(2026, 10, 11)) == ("openrouter/a",)
    price = await usage.add_price(
        provider="openrouter",
        model="a",
        usd_per_mtok_in=Decimal("2"),
        usd_per_mtok_out=Decimal("10"),
        effective_from=date(2026, 1, 1),
        actor="user:root",
    )
    assert price.state == "current"
    report = await usage.report(query)
    assert report.total_cost == Decimal("4.000000") and not report.incomplete  # 2 + (1 + 1)
    assert [day.day for day in report.days] == [date(2026, 10, 10), date(2026, 10, 11)]
    by_assistant = await usage.report(
        UsageQuery(start=date(2026, 10, 10), end=date(2026, 10, 11), by="assistant", origin="all")
    )
    assert {row.key: row.requests for row in by_assistant.totals} == {"geral": 3}


async def test_periodo_anterior(stores: Stores) -> None:
    usage = UsageService(store=stores.usage, prices=stores.prices, clock=MovingClock(DAY))
    await usage.add_price(
        provider="openrouter",
        model="a",
        usd_per_mtok_in=Decimal("1"),
        usd_per_mtok_out=Decimal("0"),
        effective_from=date(2026, 1, 1),
        actor="cli",
    )
    await _emit(stores, at=DAY - timedelta(days=7), request_id="antes", input_tokens=1_000_000, output_tokens=0)
    report = await usage.report(UsageQuery(start=date(2026, 10, 4), end=date(2026, 10, 10)))
    assert report.total_cost == Decimal(0) and report.previous_total_cost == Decimal("1.000000")


async def test_preco_invalido(stores: Stores) -> None:
    usage = UsageService(store=stores.usage, prices=stores.prices, clock=MovingClock(DAY))
    with pytest.raises(InvalidPrice) as caught:
        await usage.add_price(
            provider="openrouter",
            model="a",
            usd_per_mtok_in=Decimal("-1"),
            usd_per_mtok_out=Decimal("0"),
            effective_from=date(2026, 1, 1),
            actor="cli",
        )
    assert caught.value.field == "input"
    with pytest.raises(InvalidPrice):
        await usage.add_price(
            provider="",
            model="a",
            usd_per_mtok_in=Decimal("1"),
            usd_per_mtok_out=Decimal("0"),
            effective_from=date(2026, 1, 1),
            actor="cli",
        )


async def test_destino_de_uso_falha_conta_e_nao_propaga(stores: Stores) -> None:
    class Broken:
        async def append(self, calls: object, executions: object) -> None:
            raise OSError("banco fora do ar")

    destination = UsageDestination(store=Broken(), origin="production", clock=FixedClock(DAY))  # type: ignore[arg-type]
    primary = InMemoryTraceBackend()
    trace = TraceService(exporter=primary, reader=primary, clock=FixedClock(DAY), destinations=(destination,))
    trace.emit(started())
    trace.emit(model_call())
    await trace.flush()
    stats = destination.stats()
    assert stats.dropped == 2 and stats.last_error is not None and stats.queued == 0
