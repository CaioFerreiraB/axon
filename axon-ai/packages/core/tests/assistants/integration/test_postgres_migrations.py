"""T050 — migrações do schema `assistants` contra um Postgres real (ADR-015). Pulado sem `AXON_TEST_POSTGRES_DSN`."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from assistants_testkit import T0

from axon_ai.assistants.adapters import postgres_schema
from axon_ai.assistants.adapters.postgres_schema import MigrationError, migrate


async def _scalar_rows(pool: Any, query: str) -> list[Any]:
    async with pool.connection() as connection:
        cursor = await connection.execute(query)
        return [row[0] for row in await cursor.fetchall()]


async def test_banco_vazio_recebe_o_schema_e_as_versoes(pg_pool: Any) -> None:
    assert await migrate(pg_pool, now=T0) == (1, 2, 3)
    assert await _scalar_rows(pg_pool, "SELECT version FROM assistants.schema_version ORDER BY version") == [1, 2, 3]
    tabelas = await _scalar_rows(
        pg_pool, "SELECT table_name FROM information_schema.tables WHERE table_schema = 'assistants' ORDER BY 1"
    )
    assert tabelas == [
        "api_keys",
        "schema_version",
        "system_override_history",
        "system_overrides",
        "user_assistants",
    ]


async def test_rodar_de_novo_nao_reaplica(pg_pool: Any) -> None:
    await migrate(pg_pool, now=T0)
    assert await migrate(pg_pool, now=T0) == ()


async def test_duas_chamadas_concorrentes_aplicam_uma_vez(pg_pool: Any) -> None:
    resultados = await asyncio.gather(migrate(pg_pool, now=T0), migrate(pg_pool, now=T0))
    assert sorted(resultados) == [(), (1, 2, 3)]
    assert await _scalar_rows(pg_pool, "SELECT count(*) FROM assistants.schema_version") == [3]


async def test_nenhuma_tabela_fora_do_schema_do_modulo(pg_pool: Any) -> None:
    """Cada módulo tem a própria `schema_version` no próprio schema (ADR-015); as tabelas da 003 só existem no dela."""
    await migrate(pg_pool, now=T0)
    schemas = await _scalar_rows(
        pg_pool,
        "SELECT DISTINCT table_schema FROM information_schema.tables "
        "WHERE table_name IN ('api_keys', 'user_assistants')",
    )
    assert schemas == ["assistants"]


async def test_migracao_quebrada_nomeia_modulo_e_arquivo(
    pg_pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "001_quebrada.sql").write_text("CREATE TABLE assistants.x (", encoding="utf-8")
    monkeypatch.setattr(postgres_schema, "MIGRATIONS", tmp_path)
    with pytest.raises(MigrationError, match=r"assistants: a migração 001_quebrada\.sql falhou"):
        await migrate(pg_pool, now=T0)
