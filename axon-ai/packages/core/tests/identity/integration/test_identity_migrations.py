"""T090 — US9: a migração 005 do schema `identity` sobre uma instalação com contas (ADR-015, research R28). Pulado sem
`AXON_TEST_POSTGRES_DSN`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
import pytest
from identity_testkit import T0

from axon_ai.identity.adapters import postgres_schema
from axon_ai.identity.adapters.postgres import PostgresAccountStore

pytestmark = pytest.mark.us9


async def test_005_sobre_contas_existentes(pg_pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for arquivo in sorted(postgres_schema.MIGRATIONS.glob("00[1234]_*.sql")):
        (tmp_path / arquivo.name).write_text(arquivo.read_text(encoding="utf-8"), encoding="utf-8")
    real = postgres_schema.MIGRATIONS
    monkeypatch.setattr(postgres_schema, "MIGRATIONS", tmp_path)
    await postgres_schema.migrate(pg_pool, now=T0)
    async with pg_pool.connection() as connection:
        await connection.execute(
            "INSERT INTO identity.accounts (id, username, email, name, active, temporary_password, created_at, "
            "updated_at, version) VALUES ('id-ana', 'ana', 'ana@exemplo.org', 'Ana', true, false, %s, %s, 1)",
            (T0, T0),
        )
    monkeypatch.setattr(postgres_schema, "MIGRATIONS", real)

    assert 5 in await postgres_schema.migrate(pg_pool, now=T0)

    record = await PostgresAccountStore(pg_pool).by_username("ana")
    assert record is not None and record.deletion_pseudonym is None and not record.account.deleting
    with pytest.raises(psycopg.errors.CheckViolation):
        async with pg_pool.connection() as connection:
            await connection.execute("UPDATE identity.accounts SET deletion_pseudonym = 'deleted:xyz'")
