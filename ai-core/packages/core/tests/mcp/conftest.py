"""Fixtures da 007. As fábricas ficam em `mcp_testkit`; aqui mora só o que tem ciclo de vida.

O Postgres real entra quando `AI_CORE_TEST_POSTGRES_DSN` está definida (a CI do core a define, ADR-015). Sem ela, os
casos do adapter real são pulados com motivo explícito.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from mcp_testkit import T0, serving

PG_DSN = os.environ.get("AI_CORE_TEST_POSTGRES_DSN")
SKIP_PG = "defina AI_CORE_TEST_POSTGRES_DSN para rodar contra um Postgres real (quickstart.md)"


@pytest.fixture
async def pg_pool() -> AsyncIterator[Any]:
    """Pool do Postgres de teste, com o schema `mcp` recriado e migrado a cada teste."""
    if PG_DSN is None:
        pytest.skip(SKIP_PG)
    from psycopg_pool import AsyncConnectionPool

    from ai_core.mcp.adapters.postgres_schema import migrate

    pool = AsyncConnectionPool(PG_DSN, open=False, min_size=1, max_size=4)
    await pool.open()
    async with pool.connection() as connection:
        await connection.execute("DROP SCHEMA IF EXISTS mcp CASCADE")
    await migrate(pool, now=T0)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture(params=["memoria", "postgres"])
def server_store(request: pytest.FixtureRequest) -> Any:
    """`McpServerStore` nas duas versões: a conformidade roda contra as duas (princípio XIII)."""
    if request.param == "memoria":
        from ai_core.mcp.adapters.memory import InMemoryServerStore

        return InMemoryServerStore()
    from ai_core.mcp.adapters.registry_postgres import PostgresServerStore

    return PostgresServerStore(request.getfixturevalue("pg_pool"))


@pytest.fixture
def demo_http() -> Iterator[str]:
    """O servidor de demonstração por Streamable HTTP; devolve o endpoint."""
    from servers.demo import http_app

    with serving(http_app()) as port:
        yield f"http://127.0.0.1:{port}/mcp"


@pytest.fixture
def demo_sse() -> Iterator[str]:
    """O servidor de demonstração por HTTP+SSE; devolve o endpoint."""
    from servers.demo import sse_app

    with serving(sse_app()) as port:
        yield f"http://127.0.0.1:{port}/sse"
