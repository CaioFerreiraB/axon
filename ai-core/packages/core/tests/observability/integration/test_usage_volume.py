"""T060 — SC-008: 100 mil chamadas em 90 dias no Postgres de teste; o relatório de 90 dias responde em menos de 1 s."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from trace_testkit import MovingClock

from ai_core.observability.adapters.postgres import PostgresPriceStore, PostgresUsageStore
from ai_core.observability.api import UsageQuery
from ai_core.observability.ports import ModelCallRow
from ai_core.observability.service import UsageService

pytestmark = pytest.mark.us5

START = datetime(2026, 7, 1, 3, tzinfo=UTC)  # meia-noite em São Paulo
MODELS = ("openai/gpt-4.1-mini", "nvidia/nemotron", "meta/llama", "qwen/qwen3")
ASSISTANTS = ("geral", "scouting", "interno", None)


async def test_relatorio_de_90_dias_com_100_mil_chamadas(migrated_pool: Any) -> None:
    store = PostgresUsageStore(migrated_pool)
    rows = [
        ModelCallRow(
            request_id=f"r{index // 2}",
            at=START + timedelta(seconds=index * 77),
            origin="production",
            assistant=ASSISTANTS[index % 4],
            provider="openrouter",
            model=MODELS[index % 4],
            role="generation",
            input_tokens=800,
            output_tokens=120,
            duration_ms=900.0,
        )
        for index in range(100_000)
    ]
    for batch in range(0, len(rows), 10_000):
        await store.append(rows[batch : batch + 10_000], [])
    usage = UsageService(store=store, prices=PostgresPriceStore(migrated_pool), clock=MovingClock(START))
    query = UsageQuery(start=date(2026, 7, 1), end=date(2026, 9, 28), tz="America/Sao_Paulo")
    began = time.perf_counter()
    report = await usage.report(query)
    elapsed = time.perf_counter() - began
    assert sum(row.calls for row in report.totals) == 100_000
    assert report.requests == 50_000 and len(report.days) == 90
    assert elapsed < 1.0, elapsed
