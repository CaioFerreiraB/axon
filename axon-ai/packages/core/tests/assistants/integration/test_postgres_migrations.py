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
    assert await migrate(pg_pool, now=T0) == (1, 2, 3, 4, 5)
    assert await _scalar_rows(pg_pool, "SELECT version FROM assistants.schema_version ORDER BY version") == [
        1,
        2,
        3,
        4,
        5,
    ]
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
    assert sorted(resultados) == [(), (1, 2, 3, 4, 5)]
    assert await _scalar_rows(pg_pool, "SELECT count(*) FROM assistants.schema_version") == [5]


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


async def _migrate_until_003(pg_pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Aplica só as migrações até a 003, como numa instalação de antes do ADR-040."""
    for arquivo in sorted(postgres_schema.MIGRATIONS.glob("00[123]_*.sql")):
        (tmp_path / arquivo.name).write_text(arquivo.read_text(encoding="utf-8"), encoding="utf-8")
    real = postgres_schema.MIGRATIONS
    monkeypatch.setattr(postgres_schema, "MIGRATIONS", tmp_path)
    assert await migrate(pg_pool, now=T0) == (1, 2, 3)
    monkeypatch.setattr(postgres_schema, "MIGRATIONS", real)


@pytest.mark.us12
async def test_004_aplica_sobre_chaves_existentes(
    pg_pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from axon_ai.assistants.adapters.api_keys_postgres import PostgresApiKeyStore
    from axon_ai.assistants.domain.keys import hash_key

    await _migrate_until_003(pg_pool, tmp_path, monkeypatch)
    async with pg_pool.connection() as connection:
        await connection.execute(
            "INSERT INTO assistants.api_keys (key_id, key_hash, subject, created_at) VALUES (%s, %s, %s, %s)",
            ("00000000000000d1", hash_key("axn_00000000000000d1_s"), "svc:antigo", T0),
        )

    assert await migrate(pg_pool, now=T0) == (4, 5)
    record = await PostgresApiKeyStore(pg_pool).get("00000000000000d1")
    assert record is not None and record.info.rotated_at is None and record.info.active
    assert record.key_hash == hash_key("axn_00000000000000d1_s")


@pytest.mark.us13
async def test_005_aplica_sobre_sobreposicoes_e_passa_a_aceitar_auth(
    pg_pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import psycopg

    await _migrate_until_003(pg_pool, tmp_path, monkeypatch)
    insert = (
        "INSERT INTO assistants.system_overrides (assistant, section, payload, fingerprint, version, updated_by, "
        "updated_at) VALUES (%s, %s, '{}'::jsonb, 'f', 1, 'user:caio', %s)"
    )
    async with pg_pool.connection() as connection:
        await connection.execute(insert, ("geral", "models", T0))
        await connection.execute(insert, ("geral", "mcp", T0))

    assert await migrate(pg_pool, now=T0) == (4, 5)
    async with pg_pool.connection() as connection:
        await connection.execute(insert, ("geral", "auth", T0))
    secoes = await _scalar_rows(pg_pool, "SELECT section FROM assistants.system_overrides ORDER BY section")
    assert secoes == ["auth", "mcp", "models"]
    with pytest.raises(psycopg.errors.CheckViolation):
        async with pg_pool.connection() as connection:
            await connection.execute(insert, ("geral", "visibility", T0))
