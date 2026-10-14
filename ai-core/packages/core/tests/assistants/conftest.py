"""Fixtures da 003. As fábricas ficam em `assistants_testkit`; aqui mora só o que tem ciclo de vida.

O Postgres real entra quando `AI_CORE_TEST_POSTGRES_DSN` está definida (a CI do core a define, ADR-015). Sem ela, os
casos do adapter real são pulados com motivo explícito — como o Ollama da 006.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from assistants_testkit import T0, MutableClock

PG_DSN = os.environ.get("AI_CORE_TEST_POSTGRES_DSN")
SKIP_PG = "defina AI_CORE_TEST_POSTGRES_DSN para rodar contra um Postgres real (quickstart.md)"


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock()


@pytest.fixture
async def pg_pool() -> AsyncIterator[Any]:
    """Pool do Postgres de teste, com o schema `assistants` recriado do zero a cada teste."""
    if PG_DSN is None:
        pytest.skip(SKIP_PG)
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(PG_DSN, open=False, min_size=1, max_size=4)
    await pool.open()
    async with pool.connection() as connection:
        await connection.execute("DROP SCHEMA IF EXISTS assistants CASCADE")
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def migrated_pool(pg_pool: Any) -> Any:
    from ai_core.assistants.adapters.postgres_schema import migrate

    await migrate(pg_pool, now=T0)
    return pg_pool


@pytest.fixture(params=["memoria", "postgres"])
def api_key_store(request: pytest.FixtureRequest) -> Any:
    """`ApiKeyStore` nas duas versões: a conformidade roda contra as duas (princípio XIII)."""
    if request.param == "memoria":
        from ai_core.assistants.adapters.memory import InMemoryApiKeyStore

        return InMemoryApiKeyStore()
    from ai_core.assistants.adapters.api_keys_postgres import PostgresApiKeyStore

    return PostgresApiKeyStore(request.getfixturevalue("migrated_pool"))


@pytest.fixture(params=["memoria", "postgres"])
def user_assistant_store(request: pytest.FixtureRequest) -> Any:
    """`UserAssistantStore` nas duas versões."""
    if request.param == "memoria":
        from ai_core.assistants.adapters.memory import InMemoryUserAssistantStore

        return InMemoryUserAssistantStore()
    from ai_core.assistants.adapters.assistants_postgres import PostgresUserAssistantStore

    return PostgresUserAssistantStore(request.getfixturevalue("migrated_pool"))


@pytest.fixture(params=["memoria", "postgres"])
def override_store(request: pytest.FixtureRequest) -> Any:
    """`SystemOverrideStore` nas duas versões (Fase 9, ADR-032)."""
    if request.param == "memoria":
        from ai_core.assistants.adapters.memory import InMemorySystemOverrideStore

        return InMemorySystemOverrideStore()
    from ai_core.assistants.adapters.overrides_postgres import PostgresSystemOverrideStore

    return PostgresSystemOverrideStore(request.getfixturevalue("migrated_pool"))
