"""T056 — conformidade do `UsageStore` e do `PriceStore` (memória e Postgres): a mesma agregação nos dois."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from conftest import Stores
from trace_testkit import AT

from ai_core.observability.api import Price, UsageQuery
from ai_core.observability.domain.usage import window
from ai_core.observability.ports import ExecutionRow, ModelCallRow

pytestmark = pytest.mark.us5


def _call(
    at: datetime,
    rid: str,
    *,
    model: str = "a",
    assistant: str | None = "geral",
    origin: str = "production",
    reported_cost: Decimal | None = None,
) -> ModelCallRow:
    return ModelCallRow(
        request_id=rid,
        at=at,
        origin=origin,  # type: ignore[arg-type]
        assistant=assistant,
        provider="openrouter",
        model=model,
        role="generation",
        input_tokens=100,
        output_tokens=10,
        duration_ms=5.0,
        reported_cost=reported_cost,
    )


async def _daily(stores: Stores, query: UsageQuery) -> Any:
    start, end = window(query)
    return await stores.usage.daily(start=start, end=end, tz=query.tz, by=query.by, origin=query.origin)


async def test_agregado_por_dia_local_chave_e_requisicoes_distintas(stores: Stores) -> None:
    late = datetime(2026, 10, 14, 2, 30, tzinfo=UTC)  # dia 13 em São Paulo
    calls = [
        _call(late, "r1"),
        _call(late + timedelta(minutes=1), "r1", model="b"),
        _call(datetime(2026, 10, 14, 15, tzinfo=UTC), "r2"),
        _call(datetime(2026, 10, 14, 16, tzinfo=UTC), "r3", assistant=None, origin="evaluation"),
    ]
    await stores.usage.append(calls, [])
    query = UsageQuery(start=date(2026, 10, 13), end=date(2026, 10, 14), tz="America/Sao_Paulo", by="model")
    agg = await _daily(stores, query)
    assert [(t.day, t.key, t.calls, t.input_tokens) for t in agg.tokens] == [
        (date(2026, 10, 13), "openrouter/a", 1, 100),
        (date(2026, 10, 13), "openrouter/b", 1, 100),
        (date(2026, 10, 14), "openrouter/a", 1, 100),
    ]
    assert agg.total_requests == 2
    by_assistant = await _daily(
        stores,
        UsageQuery(
            start=date(2026, 10, 13), end=date(2026, 10, 14), tz="America/Sao_Paulo", by="assistant", origin="all"
        ),
    )
    assert {(k.key, k.requests) for k in by_assistant.key_requests} == {("geral", 2), (None, 1)}
    assert by_assistant.total_requests == 3


async def test_custo_informado_e_somado_a_parte(stores: Stores) -> None:
    """ADR-035: a parte com custo informado tem contagem, tokens e soma próprias, em `Decimal` exato."""
    at = datetime(2026, 10, 14, 15, tzinfo=UTC)
    calls = [
        _call(at, "r1", reported_cost=Decimal("0.0000425")),
        _call(at + timedelta(minutes=1), "r2", reported_cost=Decimal("0.0012")),
        _call(at + timedelta(minutes=2), "r3"),
    ]
    await stores.usage.append(calls, [])
    agg = await _daily(stores, UsageQuery(start=date(2026, 10, 14), end=date(2026, 10, 14), by="model"))
    (group,) = agg.tokens
    assert (group.calls, group.input_tokens, group.output_tokens) == (3, 300, 30)
    assert (group.reported_calls, group.reported_input_tokens, group.reported_output_tokens) == (2, 200, 20)
    assert group.reported_cost == Decimal("0.0012425")


async def test_execucoes_sao_atualizadas_e_o_expurgo_tira_o_antigo(stores: Stores) -> None:
    start = ExecutionRow(request_id="r1", started_at=AT, origin="production", assistant="geral", flow="chat")
    await stores.usage.append([_call(AT, "r1")], [start])
    await stores.usage.append(
        [],
        [
            ExecutionRow(
                request_id="r1",
                started_at=AT,
                origin="production",
                assistant="geral",
                flow="chat",
                finished_at=AT,
                ok=True,
                duration_ms=12.0,
            )
        ],
    )
    await stores.usage.append([_call(AT + timedelta(days=10), "r9")], [])
    removed = await stores.usage.purge(before=AT + timedelta(days=1))
    assert removed == 2  # a chamada e a execução antigas
    query = UsageQuery(start=AT.date(), end=(AT + timedelta(days=10)).date(), by="model", origin="all")
    assert (await _daily(stores, query)).total_requests == 1


async def test_precos_com_vigencia_repetida_substitui(stores: Stores) -> None:
    def price(inp: str, since: date) -> Price:
        return Price(
            provider="ollama",
            model="m",
            usd_per_mtok_in=Decimal(inp),
            usd_per_mtok_out=Decimal("0"),
            effective_from=since,
            created_by="cli",
            created_at=AT,
        )

    await stores.prices.add(price("1", date(2026, 1, 1)))
    await stores.prices.add(price("2", date(2026, 6, 1)))
    await stores.prices.add(price("3", date(2026, 6, 1)))
    stored = await stores.prices.all()
    assert [(p.effective_from, p.usd_per_mtok_in) for p in stored] == [
        (date(2026, 1, 1), Decimal("1")),
        (date(2026, 6, 1), Decimal("3")),
    ]


async def test_ajustes_dos_destinos_com_versao(stores: Stores) -> None:
    from ai_core.observability.ports import DestinationSettings

    assert await stores.settings.get() == DestinationSettings()
    first = DestinationSettings(
        langfuse_enabled=True,
        langfuse_host="https://lf.exemplo.org",
        langfuse_secret_sealed=b"\x01x",
        version=1,
        updated_by="user:root",
        updated_at=AT,
    )
    assert await stores.settings.put(first, expected_version=0)
    assert not await stores.settings.put(first, expected_version=0)
    stored = await stores.settings.get()
    assert (
        stored.langfuse_secret_sealed == b"\x01x"
        and stored.version == 1
        and stored.langfuse_host == "https://lf.exemplo.org"
    )
