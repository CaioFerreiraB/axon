"""T098 — SC-011: 100 mil chamadas estimadas em 400 dias no Postgres de teste; o relatório por mês responde em menos de
1 s (009 US9)."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from axon_ai.observability.adapters.memory import FixedClock, FixedImpactEstimator
from axon_ai.observability.adapters.postgres import PostgresUsageStore
from axon_ai.observability.api import ImpactQuery
from axon_ai.observability.ports import ModelCallRow
from axon_ai.observability.service import ImpactService

pytestmark = pytest.mark.us9

START = datetime(2025, 10, 1, 3, tzinfo=UTC)  # meia-noite em São Paulo
MODELS = ("openai/gpt-4.1-mini", "z-ai/glm-5.3-flash", "meta/llama", "qwen/qwen3")
ASSISTANTS = ("geral", "scouting", "interno", None)


async def test_relatorio_de_400_dias_com_100_mil_chamadas(migrated_pool: Any) -> None:
    store = PostgresUsageStore(migrated_pool)
    estimator = FixedImpactEstimator(version="0.11.3", unknown=("qwen/qwen3",))
    step = timedelta(days=400) / 100_000
    rows = []
    for index in range(100_000):
        model = MODELS[index % 4]
        impact = estimator.estimate("openrouter", model, 120, 0.9)
        rows.append(
            ModelCallRow(
                request_id=f"r{index // 2}",
                at=START + step * index,
                origin="production",
                assistant=ASSISTANTS[index % 4],
                provider="openrouter",
                model=model,
                role="generation",
                input_tokens=800,
                output_tokens=120,
                duration_ms=900.0,
                impact=impact,
                impact_tried=True,
            )
        )
    for batch in range(0, len(rows), 10_000):
        await store.append(rows[batch : batch + 10_000], [])
    # Em produção o autovacuum mantém as estatísticas; logo depois de uma carga em massa, sem elas, o planejador
    # agrega por ordenação, e o tempo medido não é o de uma instalação em uso.
    async with migrated_pool.connection() as connection:
        await connection.execute("ANALYZE observability.model_calls")
    service = ImpactService(store=store, clock=FixedClock(START + timedelta(days=400)), estimator=estimator)
    query = ImpactQuery(start=date(2025, 10, 1), end=date(2026, 11, 4), tz="America/Sao_Paulo", grain="month")
    began = time.perf_counter()
    report = await service.report(query)
    elapsed = time.perf_counter() - began
    assert report.totals is not None
    assert report.totals.coverage.calls == 100_000
    assert report.totals.coverage.estimated == 75_000
    assert len(report.buckets) == 14
    assert elapsed < 1.0, elapsed
