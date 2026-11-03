"""T092 — a estimativa no esvaziamento do destino de uso e o preenchimento (009 US9; research R46, R50)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from trace_testkit import AT, model_call, started

from axon_ai.observability.adapters.memory import FixedClock, FixedImpactEstimator, InMemoryUsageStore
from axon_ai.observability.adapters.usage import UsageDestination
from axon_ai.observability.domain.records import to_record
from axon_ai.observability.domain.usage_records import ModelCallRow
from axon_ai.observability.service import ImpactService

pytestmark = pytest.mark.us9


def _destination(store: InMemoryUsageStore, estimator: FixedImpactEstimator | None) -> UsageDestination:
    return UsageDestination(store=store, origin="production", clock=FixedClock(AT), estimator=estimator)


def _feed(destination: UsageDestination) -> None:
    destination.export(to_record(started("r1"), at=AT))
    destination.export(to_record(model_call("r1", model="openai/gpt-4.1-mini", output_tokens=50), at=AT))
    destination.export(to_record(model_call("r1", model="qwen3:1.7b", output_tokens=50), at=AT))
    destination.export(to_record(model_call("r1", model="openai/gpt-4.1-mini", output_tokens=0), at=AT))
    destination.export(
        to_record(model_call("r1", model="openai/gpt-4.1-mini", output_tokens=50, finish_reason="error"), at=AT)
    )


async def test_flush_estima_as_elegiveis_e_marca_as_sem_par() -> None:
    store = InMemoryUsageStore()
    estimator = FixedImpactEstimator(version="0.11.3", unknown=("qwen3:1.7b",))
    destination = _destination(store, estimator)
    _feed(destination)
    await destination.flush()
    estimated, unmatched, no_tokens, failed = store.calls
    assert estimated.impact is not None and estimated.impact_tried
    assert unmatched.impact is None and unmatched.impact_tried
    assert no_tokens.impact is None and not no_tokens.impact_tried
    assert failed.impact is None and not failed.impact_tried
    assert destination.stats().impact_failed == 0


async def test_estimador_que_levanta_nao_derruba_o_lote() -> None:
    store = InMemoryUsageStore()
    destination = _destination(store, FixedImpactEstimator(version="0.11.3", raises=True))
    _feed(destination)
    await destination.flush()
    assert len(store.calls) == 4
    assert all(row.impact is None and not row.impact_tried for row in store.calls)
    assert destination.stats().impact_failed == 2


async def test_sem_estimador_nada_e_tentado() -> None:
    store = InMemoryUsageStore()
    destination = _destination(store, None)
    _feed(destination)
    await destination.flush()
    assert all(not row.impact_tried for row in store.calls)


async def test_preenchimento_estima_as_nulas_uma_vez() -> None:
    store = InMemoryUsageStore()
    old = [
        ModelCallRow(
            request_id=f"r{index}",
            at=datetime(2026, 10, 1, tzinfo=UTC),
            origin="production",
            assistant="geral",
            provider="openrouter",
            model=model,
            role="generation",
            input_tokens=10,
            output_tokens=20,
            duration_ms=1000.0,
        )
        for index, model in enumerate(["openai/gpt-4.1-mini", "qwen3:1.7b", "openai/gpt-4.1-nano"])
    ]
    await store.append(old, [])
    service = ImpactService(
        store=store,
        clock=FixedClock(AT),
        estimator=FixedImpactEstimator(version="0.11.3", unknown=("qwen3:1.7b",)),
    )
    result = await service.backfill(limit=10, batch=2)
    assert (result.estimated, result.unmatched, result.failed) == (2, 1, 0)
    again = await service.backfill(limit=10)
    assert (again.estimated, again.unmatched, again.failed) == (0, 0, 0)
    failing = ImpactService(
        store=InMemoryUsageStore(), clock=FixedClock(AT), estimator=FixedImpactEstimator(version="0.11.3", raises=True)
    )
    await failing._store.append(old, [])  # type: ignore[attr-defined]
    assert (await failing.backfill(limit=10)).failed == 3
