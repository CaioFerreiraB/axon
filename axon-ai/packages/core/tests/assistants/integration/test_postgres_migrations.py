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
    assert await migrate(pg_pool, now=T0) == (1, 2, 3, 4, 5, 6)
    assert await _scalar_rows(pg_pool, "SELECT version FROM assistants.schema_version ORDER BY version") == [
        1,
        2,
        3,
        4,
        5,
        6,
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
    assert sorted(resultados) == [(), (1, 2, 3, 4, 5, 6)]
    assert await _scalar_rows(pg_pool, "SELECT count(*) FROM assistants.schema_version") == [6]


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

    assert await migrate(pg_pool, now=T0) == (4, 5, 6)
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

    assert await migrate(pg_pool, now=T0) == (4, 5, 6)
    async with pg_pool.connection() as connection:
        await connection.execute(insert, ("geral", "auth", T0))
    secoes = await _scalar_rows(pg_pool, "SELECT section FROM assistants.system_overrides ORDER BY section")
    assert secoes == ["auth", "mcp", "models"]
    with pytest.raises(psycopg.errors.CheckViolation):
        async with pg_pool.connection() as connection:
            await connection.execute(insert, ("geral", "visibility", T0))


async def _migrate_until(pg_pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, last: int) -> None:
    """Aplica só as migrações até `last`, como numa instalação anterior."""
    for arquivo in sorted(postgres_schema.MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
        if int(arquivo.name[:3]) <= last:
            (tmp_path / arquivo.name).write_text(arquivo.read_text(encoding="utf-8"), encoding="utf-8")
    real = postgres_schema.MIGRATIONS
    monkeypatch.setattr(postgres_schema, "MIGRATIONS", tmp_path)
    assert await migrate(pg_pool, now=T0) == tuple(range(1, last + 1))
    monkeypatch.setattr(postgres_schema, "MIGRATIONS", real)


_CHAVES_ANTIGAS = (
    ("00000000000000e1", "svc:comum", []),
    ("00000000000000e2", "user:caio", ["operadores"]),
    ("00000000000000e3", "user:ana", ["equipe"]),
)


async def _insert_old_keys(pg_pool: Any) -> None:
    from axon_ai.assistants.domain.keys import hash_key

    async with pg_pool.connection() as connection:
        for key_id, subject, groups in _CHAVES_ANTIGAS:
            await connection.execute(
                "INSERT INTO assistants.api_keys (key_id, key_hash, subject, groups, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (key_id, hash_key(f"axn_{key_id}_s"), subject, groups, T0),
            )


@pytest.mark.us14
async def test_006_preenche_os_escopos_com_o_grupo_de_administracao(
    pg_pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import psycopg
    from assistants_testkit import access_service

    from axon_ai.assistants.adapters.api_keys_postgres import PostgresApiKeyStore
    from axon_ai.assistants.domain.access import can_infer

    await _migrate_until(pg_pool, tmp_path, monkeypatch, 5)
    await _insert_old_keys(pg_pool)

    assert await migrate(pg_pool, now=T0, admin_group="operadores") == (6,)
    store = PostgresApiKeyStore(pg_pool)
    escopos = {record.info.key_id: record.info.scopes for record in await store.list()}
    assert escopos == {
        "00000000000000e1": frozenset({"inference"}),
        "00000000000000e2": frozenset({"inference", "admin"}),
        "00000000000000e3": frozenset({"inference"}),
    }

    # SC-011: cada chave autentica com o mesmo acesso de antes.
    access = access_service(keys=store, admin_group="operadores")
    for key_id, _, groups in _CHAVES_ANTIGAS:
        principal = await access.authenticate(surface="private", credential=f"axn_{key_id}_s")
        assert principal is not None and can_infer(principal)
        assert access.is_admin(principal) is ("operadores" in groups)

    insert = (
        "INSERT INTO assistants.api_keys (key_id, key_hash, subject, created_at, scopes) VALUES (%s, %s, %s, %s, %s)"
    )
    with pytest.raises(psycopg.errors.NotNullViolation):
        async with pg_pool.connection() as connection:
            await connection.execute(insert, ("00000000000000e4", b"h", "svc:x", T0, None))
    for invalido in ([], ["root"]):
        with pytest.raises(psycopg.errors.CheckViolation):
            async with pg_pool.connection() as connection:
                await connection.execute(insert, ("00000000000000e5", b"h", "svc:x", T0, invalido))


@pytest.mark.us14
async def test_006_sem_grupo_de_administracao_da_inference_a_todas(
    pg_pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _migrate_until(pg_pool, tmp_path, monkeypatch, 5)
    await _insert_old_keys(pg_pool)

    assert await migrate(pg_pool, now=T0) == (6,)
    assert await _scalar_rows(pg_pool, "SELECT DISTINCT scopes FROM assistants.api_keys") == [["inference"]]
