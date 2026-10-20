"""Fixtures da 004. As fábricas ficam em `capabilities_testkit`; aqui mora só o que tem ciclo de vida.

O Postgres real entra quando `AXON_TEST_POSTGRES_DSN` está definida (ADR-015); sem ela, os casos do adapter real
são pulados com motivo explícito.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from capabilities_testkit import T0

PG_DSN = os.environ.get("AXON_TEST_POSTGRES_DSN")
SKIP_PG = "defina AXON_TEST_POSTGRES_DSN para rodar contra um Postgres real (quickstart.md)"


@pytest.fixture
async def pg_pool() -> AsyncIterator[Any]:
    """Pool do Postgres de teste, com o schema `capabilities` recriado e migrado a cada teste."""
    if PG_DSN is None:
        pytest.skip(SKIP_PG)
    from psycopg_pool import AsyncConnectionPool

    from axon_ai.capabilities.adapters.postgres_schema import migrate

    pool = AsyncConnectionPool(PG_DSN, open=False, min_size=1, max_size=4)
    await pool.open()
    async with pool.connection() as connection:
        await connection.execute("DROP SCHEMA IF EXISTS capabilities CASCADE")
    await migrate(pool, now=T0)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture(params=["memoria", "postgres"])
def audit_log(request: pytest.FixtureRequest) -> Any:
    """`AuditLog` nas duas versões: a conformidade roda contra as duas (princípio XIII)."""
    if request.param == "memoria":
        from axon_ai.capabilities.adapters.memory import InMemoryAuditLog

        return InMemoryAuditLog()
    from axon_ai.capabilities.adapters.audit_postgres import PostgresAuditLog

    return PostgresAuditLog(request.getfixturevalue("pg_pool"))
