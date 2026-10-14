"""T055 — projeção do uso e o relatório: Assistant pela execução, dia local no fuso, custo por modelo e dia (R30)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from trace_testkit import AT, finished, model_call, started

from ai_core.observability.api import InvalidQuery, Price, TraceRecord, UsageQuery
from ai_core.observability.domain.records import to_record
from ai_core.observability.domain.usage import aggregate, build_report, call_row, previous, window
from ai_core.observability.ports import ModelCallRow

pytestmark = pytest.mark.us5


def _row(
    at: datetime, *, model: str = "a", assistant: str | None = "geral", rid: str = "r1", **changes: object
) -> ModelCallRow:
    fields: dict[str, object] = {
        "request_id": rid,
        "at": at,
        "origin": "production",
        "assistant": assistant,
        "provider": "openrouter",
        "model": model,
        "role": "generation",
        "input_tokens": 1_000_000,
        "output_tokens": 500_000,
        "duration_ms": 10.0,
    }
    fields.update(changes)
    return ModelCallRow(**fields)  # type: ignore[arg-type]


def _price(model: str, inp: str, out: str, since: date) -> Price:
    return Price(
        provider="openrouter",
        model=model,
        usd_per_mtok_in=Decimal(inp),
        usd_per_mtok_out=Decimal(out),
        effective_from=since,
        created_by="user:root",
        created_at=AT,
    )


def test_chamada_herda_o_assistant_da_execucao() -> None:
    record: TraceRecord = to_record(model_call(), AT)
    row = call_row(record, assistant="geral", origin="production")
    assert (row.assistant, row.provider, row.model, row.input_tokens, row.output_tokens) == (
        "geral",
        "ollama",
        "qwen3:1.7b",
        412,
        87,
    )
    assert call_row(record, assistant=None, origin="evaluation").assistant is None
    assert (
        to_record(started(), AT).type == "execution_started" and to_record(finished(), AT).type == "execution_finished"
    )


def test_dia_local_no_fuso_23h30_em_sao_paulo() -> None:
    late = datetime(2026, 10, 14, 2, 30, tzinfo=UTC)  # 23h30 do dia 13 em São Paulo
    query = UsageQuery(start=date(2026, 10, 13), end=date(2026, 10, 13), tz="America/Sao_Paulo")
    start, end = window(query)
    agg = aggregate([_row(late)], start=start, end=end, tz=query.tz, by="model", origin="production")
    assert [item.day for item in agg.tokens] == [date(2026, 10, 13)]
    utc = UsageQuery(start=date(2026, 10, 13), end=date(2026, 10, 13), tz="UTC")
    s, e = window(utc)
    assert aggregate([_row(late)], start=s, end=e, tz="UTC", by="model", origin="production").tokens == ()


def test_fuso_desconhecido_e_periodo_invalido() -> None:
    with pytest.raises(InvalidQuery) as caught:
        window(UsageQuery(start=date(2026, 1, 1), end=date(2026, 1, 2), tz="Marte/Olimpo"))
    assert caught.value.field == "tz"
    with pytest.raises(InvalidQuery):
        UsageQuery(start=date(2026, 1, 2), end=date(2026, 1, 1))
    with pytest.raises(InvalidQuery):
        UsageQuery(start=date(2025, 1, 1), end=date(2026, 1, 2))


def test_periodo_anterior_de_mesmo_tamanho() -> None:
    query = UsageQuery(start=date(2026, 10, 1), end=date(2026, 10, 7))
    assert (previous(query).start, previous(query).end) == (date(2026, 9, 24), date(2026, 9, 30))


def test_custo_pelo_preco_vigente_em_decimal_e_sem_preco_incompleto() -> None:
    day1, day2 = datetime(2026, 10, 1, 12, tzinfo=UTC), datetime(2026, 10, 2, 12, tzinfo=UTC)
    calls = [
        _row(day1, model="a", rid="r1"),
        _row(day2, model="a", rid="r2"),
        _row(day2, model="b", rid="r2"),  # o mesmo pedido chamou dois modelos
        _row(day2, model="sem-preco", rid="r3", assistant=None),
    ]
    prices = [
        _price("a", "1.5", "2", date(2026, 9, 1)),
        _price("a", "3", "4", date(2026, 10, 2)),
        _price("b", "0.1", "0.2", date(2026, 1, 1)),
    ]
    query = UsageQuery(start=date(2026, 10, 1), end=date(2026, 10, 2))
    start, end = window(query)
    agg = aggregate(calls, start=start, end=end, tz="UTC", by="model", origin="production")
    report = build_report(query, agg, prices, previous_cost=Decimal("1"))
    totals = {row.key: row for row in report.totals}
    # dia 1: 1,5 + 1 = 2,5; dia 2 (preço novo): 3 + 2 = 5
    assert totals["openrouter/a"].cost == Decimal("7.500000") and totals["openrouter/a"].priced
    assert totals["openrouter/b"].cost == Decimal("0.200000")
    assert totals["openrouter/sem-preco"].cost is None and not totals["openrouter/sem-preco"].priced
    assert report.total_cost == Decimal("7.700000") and report.incomplete
    assert report.requests == 3 and report.previous_total_cost == Decimal("1")
    assert [day.day for day in report.days] == [date(2026, 10, 1), date(2026, 10, 2)]
    by_assistant = aggregate(calls, start=start, end=end, tz="UTC", by="assistant", origin="production")
    rows = {row.key: row for row in build_report(query, by_assistant, prices).totals}
    assert rows["geral"].requests == 2 and rows["geral"].calls == 3 and rows[None].calls == 1


def test_origem_separa_avaliacao_de_producao() -> None:
    calls = [_row(AT, rid="p"), _row(AT, rid="e", origin="evaluation")]
    query = UsageQuery(start=AT.date(), end=AT.date())
    start, end = window(query)
    for origin, expected in (("production", 1), ("evaluation", 1), ("all", 2)):
        agg = aggregate(calls, start=start, end=end, tz="UTC", by="model", origin=origin)  # type: ignore[arg-type]
        assert agg.total_requests == expected


def test_sem_uso_custo_zero_e_completo() -> None:
    query = UsageQuery(start=AT.date(), end=AT.date() + timedelta(days=1))
    report = build_report(query, aggregate([], start=AT, end=AT, tz="UTC", by="model", origin="all"), [])
    assert report.total_cost == Decimal(0) and not report.incomplete and report.totals == ()
