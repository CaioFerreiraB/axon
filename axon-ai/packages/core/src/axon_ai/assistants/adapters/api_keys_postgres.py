"""`ApiKeyStore` em Postgres, no schema `assistants` (ADR-015). Só o hash é gravado (FR-015)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from psycopg_pool import AsyncConnectionPool

from axon_ai.assistants.api import ApiKeyInfo
from axon_ai.assistants.domain.keys import ApiKeyRecord

_COLUMNS = "key_id, key_hash, subject, groups, label, created_at, revoked_at, rotated_at"


def _record(row: Sequence[Any]) -> ApiKeyRecord:
    key_id, key_hash, subject, groups, label, created_at, revoked_at, rotated_at = row
    info = ApiKeyInfo(
        key_id=key_id,
        subject=subject,
        groups=frozenset(groups),
        label=label,
        created_at=created_at,
        revoked_at=revoked_at,
        rotated_at=rotated_at,
    )
    return ApiKeyRecord(info=info, key_hash=bytes(key_hash))


class PostgresApiKeyStore:
    """Chaves por `key_id`. A revogação é idempotente no próprio SQL: `COALESCE` preserva o primeiro instante; a
    rotação só alcança chave ativa, na mesma instrução (research R38)."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def add(self, record: ApiKeyRecord) -> None:
        info = record.info
        async with self._pool.connection() as connection:
            await connection.execute(
                f"INSERT INTO assistants.api_keys ({_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    info.key_id,
                    record.key_hash,
                    info.subject,
                    sorted(info.groups),
                    info.label,
                    info.created_at,
                    info.revoked_at,
                    info.rotated_at,
                ),
            )

    async def get(self, key_id: str) -> ApiKeyRecord | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_COLUMNS} FROM assistants.api_keys WHERE key_id = %s", (key_id,)
            )
            row = await cursor.fetchone()
        return _record(row) if row is not None else None

    async def list(self) -> Sequence[ApiKeyRecord]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(f"SELECT {_COLUMNS} FROM assistants.api_keys ORDER BY created_at, key_id")
            rows = await cursor.fetchall()
        return [_record(row) for row in rows]

    async def revoke(self, key_id: str, *, at: datetime) -> ApiKeyRecord | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "UPDATE assistants.api_keys SET revoked_at = COALESCE(revoked_at, %s) "
                f"WHERE key_id = %s RETURNING {_COLUMNS}",
                (at, key_id),
            )
            row = await cursor.fetchone()
        return _record(row) if row is not None else None

    async def rotate(self, key_id: str, *, key_hash: bytes, at: datetime) -> ApiKeyRecord | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "UPDATE assistants.api_keys SET key_hash = %s, rotated_at = %s "
                f"WHERE key_id = %s AND revoked_at IS NULL RETURNING {_COLUMNS}",
                (key_hash, at, key_id),
            )
            row = await cursor.fetchone()
        return _record(row) if row is not None else None
