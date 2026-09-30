"""Fixtures dos testes da 008. As fábricas ficam em `http_testkit`.

O Postgres real das conversas entra quando `AI_CORE_TEST_POSTGRES_DSN` está definida (a CI do core a define, ADR-015);
sem ela, os casos do adapter real são pulados com motivo explícito.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from graph_testkit import RecordingTraceSink
from http_testkit import CREATED, app

PG_DSN = os.environ.get("AI_CORE_TEST_POSTGRES_DSN")


@pytest.fixture
def trace() -> RecordingTraceSink:
    return RecordingTraceSink()


@pytest.fixture
def client(trace: RecordingTraceSink) -> Iterator[TestClient]:
    with TestClient(app(trace=trace)) as test_client:
        yield test_client


@pytest.fixture
async def http_pg_pool() -> AsyncIterator[Any]:
    """Pool do Postgres de teste com o schema `http` recriado e migrado a cada teste."""
    if PG_DSN is None:
        pytest.skip("defina AI_CORE_TEST_POSTGRES_DSN para rodar contra um Postgres real")
    from psycopg_pool import AsyncConnectionPool

    from ai_core.http.adapters.postgres_schema import migrate

    pool = AsyncConnectionPool(PG_DSN, open=False, min_size=1, max_size=4)
    await pool.open()
    async with pool.connection() as connection:
        await connection.execute("DROP SCHEMA IF EXISTS http CASCADE")
    await migrate(pool, now=CREATED)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture(params=["memoria", "postgres"])
def conversation_store(request: pytest.FixtureRequest) -> Any:
    """`ConversationStore` nas duas versões: a conformidade roda contra as duas (princípio XIII)."""
    if request.param == "memoria":
        from ai_core.http.adapters.conversations_memory import InMemoryConversationStore

        return InMemoryConversationStore()
    from ai_core.http.adapters.conversations_postgres import PostgresConversationStore

    return PostgresConversationStore(request.getfixturevalue("http_pg_pool"))
