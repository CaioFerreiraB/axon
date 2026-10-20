"""Fixtures dos testes de trace (spec 009). As fábricas ficam em `trace_testkit` (mesmo padrão de `packs_testkit`)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from trace_testkit import AT

from axon_ai.observability.adapters.memory import FixedClock, InMemoryTraceBackend
from axon_ai.observability.service import TraceService


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(AT)


@pytest.fixture
def backend() -> InMemoryTraceBackend:
    return InMemoryTraceBackend()


@pytest.fixture
def service(backend: InMemoryTraceBackend, clock: FixedClock) -> TraceService:
    return TraceService(exporter=backend, reader=backend, clock=clock)


# --- Fase 9: Postgres (ADR-015) e os armazenamentos nas duas versões --------------------------------------------------

PG_DSN = os.environ.get("AXON_TEST_POSTGRES_DSN")


@pytest.fixture
async def pg_pool() -> AsyncIterator[Any]:
    """Pool do Postgres de teste, com o schema `observability` recriado do zero a cada teste."""
    if PG_DSN is None:
        pytest.skip("defina AXON_TEST_POSTGRES_DSN para rodar contra um Postgres real")
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(PG_DSN, open=False, min_size=1, max_size=4)
    await pool.open()
    async with pool.connection() as connection:
        await connection.execute("DROP SCHEMA IF EXISTS observability CASCADE")
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def migrated_pool(pg_pool: Any) -> Any:
    from axon_ai.observability.adapters.postgres_schema import migrate

    await migrate(pg_pool, now=AT)
    return pg_pool


@dataclass
class Stores:
    usage: Any
    prices: Any
    settings: Any


@pytest.fixture(params=["memoria", "postgres"])
def stores(request: pytest.FixtureRequest) -> Stores:
    """Os três armazenamentos da Fase 9 do mesmo backend: a conformidade roda contra os dois (princípio XIII)."""
    if request.param == "memoria":
        from axon_ai.observability.adapters import memory

        return Stores(
            usage=memory.InMemoryUsageStore(),
            prices=memory.InMemoryPriceStore(),
            settings=memory.InMemoryDestinationSettingsStore(),
        )
    from axon_ai.observability.adapters import postgres

    pool = request.getfixturevalue("migrated_pool")
    return Stores(
        usage=postgres.PostgresUsageStore(pool),
        prices=postgres.PostgresPriceStore(pool),
        settings=postgres.PostgresDestinationSettingsStore(pool),
    )
