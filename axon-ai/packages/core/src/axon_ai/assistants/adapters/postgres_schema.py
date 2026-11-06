"""Migrações do schema `assistants` (ADR-015).

Arquivos SQL numerados em `sql/`, só para a frente, aplicados em ordem numa transação sob trava consultiva — dois
processos subindo juntos não aplicam a mesma migração duas vezes. A versão fica numa tabela dentro do próprio schema:
nenhum outro módulo a lê. Quem chama é a composition root, na etapa de adapters do perfil persistente.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Final

import psycopg
from psycopg_pool import AsyncConnectionPool

SCHEMA: Final = "assistants"
MIGRATIONS: Final = Path(__file__).parent / "sql"
_LOCK_KEY: Final = "axon_ai.assistants.migrate"


class MigrationError(RuntimeError):
    """Migração que falhou: o boot para, nomeando o módulo e o arquivo."""


async def _backfill_scopes(connection: psycopg.AsyncConnection, admin_group: str | None) -> None:
    """006 (research R50): as chaves anteriores aos escopos ficam com o acesso de antes — `{inference}`, e as do grupo
    de administração `{inference, admin}`. Sem grupo configurado, nenhuma administrava."""
    await connection.execute(
        f"UPDATE {SCHEMA}.api_keys SET scopes = CASE WHEN %s::text IS NOT NULL AND %s::text = ANY(groups) "
        "THEN '{inference,admin}'::text[] ELSE '{inference}'::text[] END WHERE scopes IS NULL",
        (admin_group, admin_group),
    )
    await connection.execute(f"ALTER TABLE {SCHEMA}.api_keys ALTER COLUMN scopes SET NOT NULL")


_AFTER: Final[Mapping[int, Callable[[psycopg.AsyncConnection, str | None], Awaitable[None]]]] = {6: _backfill_scopes}
"""Passos em Python que uma versão precisa e o SQL não sabe fazer, na mesma transação, logo depois do arquivo."""


async def migrate(pool: AsyncConnectionPool, *, now: datetime, admin_group: str | None = None) -> tuple[int, ...]:
    """Aplica as migrações pendentes e devolve as versões aplicadas nesta chamada. `admin_group` é o do
    `assistants.yaml`, que o preenchimento dos escopos usa (006, research R50)."""
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
                if version in _AFTER:
                    await _AFTER[version](connection, admin_group)
            except psycopg.Error as error:
                raise MigrationError(f"{SCHEMA}: a migração {path.name} falhou: {error}") from error
            await connection.execute(
                f"INSERT INTO {SCHEMA}.schema_version (version, applied_at) VALUES (%s, %s)", (version, now)
            )
            applied.append(version)
    return tuple(applied)
