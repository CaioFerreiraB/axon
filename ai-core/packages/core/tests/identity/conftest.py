"""Fixtures da 012. As fábricas ficam em `identity_testkit`; aqui mora só o que tem ciclo de vida.

O Postgres real entra quando `AI_CORE_TEST_POSTGRES_DSN` está definida (a CI do core a define, ADR-015). Sem ela, os
casos do adapter real são pulados com motivo explícito.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from identity_testkit import T0, Harness, app_for, browser, harness

PG_DSN = os.environ.get("AI_CORE_TEST_POSTGRES_DSN")
SKIP_PG = "defina AI_CORE_TEST_POSTGRES_DSN para rodar contra um Postgres real (quickstart.md)"


@pytest.fixture
async def started() -> Harness:
    """O serviço em memória, já iniciado: clientes lidos, grupo de admin e chave de assinatura criados."""
    parts = harness()
    await parts.service.start()
    return parts


@pytest.fixture
async def http(started: Harness) -> AsyncIterator[httpx.AsyncClient]:
    """Navegador em processo contra o router da 012 montado num app de teste (sem a 011, R17)."""
    async with browser(app_for(started)) as client:
        yield client


@pytest.fixture
async def pg_pool() -> AsyncIterator[Any]:
    """Pool do Postgres de teste, com o schema `identity` recriado do zero a cada teste."""
    if PG_DSN is None:
        pytest.skip(SKIP_PG)
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(PG_DSN, open=False, min_size=1, max_size=4)
    await pool.open()
    async with pool.connection() as connection:
        await connection.execute("DROP SCHEMA IF EXISTS identity CASCADE")
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def migrated_pool(pg_pool: Any) -> Any:
    from ai_core.identity.adapters.postgres_schema import migrate

    await migrate(pg_pool, now=T0)
    return pg_pool


@dataclass
class Stores:
    """Os quatro armazenamentos do mesmo backend — no Postgres, as sessões referenciam contas reais."""

    accounts: Any
    grants: Any
    keys: Any
    settings: Any


@pytest.fixture(params=["memoria", "postgres"])
def stores(request: pytest.FixtureRequest) -> Stores:
    """Armazenamentos nas duas versões: a conformidade roda contra as duas (princípio XIII)."""
    if request.param == "memoria":
        from ai_core.identity.adapters import memory

        return Stores(
            accounts=memory.InMemoryAccountStore(),
            grants=memory.InMemoryGrantStore(),
            keys=memory.InMemorySigningKeyStore(),
            settings=memory.InMemoryIdentitySettingsStore(),
        )
    from ai_core.identity.adapters import postgres

    pool = request.getfixturevalue("migrated_pool")
    return Stores(
        accounts=postgres.PostgresAccountStore(pool),
        grants=postgres.PostgresGrantStore(pool),
        keys=postgres.PostgresSigningKeyStore(pool),
        settings=postgres.PostgresIdentitySettingsStore(pool),
    )


@pytest.fixture
async def seam(stores: Stores) -> Harness:
    """O serviço iniciado sobre os armazenamentos das duas versões — para a conformidade dos seams."""
    parts = harness(stores=stores, google=True)
    await parts.service.start()
    return parts
