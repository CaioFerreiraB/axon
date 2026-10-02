"""Migrações do schema `capabilities` (ADR-015): o mesmo desenho da 003, 007 e 008 — SQL numerado em `sql/`, só para
a frente, numa transação sob trava consultiva, com a versão numa tabela dentro do próprio schema. Quem chama é a
composition root, na etapa de adapters do perfil persistente."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Final

import psycopg
from psycopg_pool import AsyncConnectionPool

SCHEMA: Final = "capabilities"
MIGRATIONS: Final = Path(__file__).parent / "sql"
_LOCK_KEY: Final = "ai_core.capabilities.migrate"


class MigrationError(RuntimeError):
    """Migração que falhou: o boot para, nomeando o módulo e o arquivo."""


async def migrate(pool: AsyncConnectionPool, *, now: datetime) -> tuple[int, ...]:
    """Aplica as migrações pendentes e devolve as versões aplicadas nesta chamada."""
    files = sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))
    applied: list[int] = []
    async with pool.connection() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (_LOCK_KEY,))
        await connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        await connection.execute(
            f"CREATE TABLE IF NOT EXISTS {SCHEMA}.schema_version "
            "(version integer PRIMARY KEY, applied_at timestamptz NOT NULL)"
        )
        cursor = await connection.execute(f"SELECT version FROM {SCHEMA}.schema_version")
        done = {row[0] for row in await cursor.fetchall()}
        for path in files:
            version = int(path.name[:3])
            if version in done:
                continue
            try:
                await connection.execute(path.read_text(encoding="utf-8").encode())
            except psycopg.Error as error:
                raise MigrationError(f"{SCHEMA}: a migração {path.name} falhou: {error}") from error
            await connection.execute(
                f"INSERT INTO {SCHEMA}.schema_version (version, applied_at) VALUES (%s, %s)", (version, now)
            )
            applied.append(version)
    return tuple(applied)
