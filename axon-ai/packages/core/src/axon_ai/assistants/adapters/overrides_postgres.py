"""`SystemOverrideStore` em Postgres, no schema `assistants` (ADR-015, ADR-032; research R30).

Gravar e descartar são uma transação com o histórico. A versão otimista é conferida no próprio comando — `INSERT … ON
CONFLICT DO NOTHING` para a primeira gravação, `UPDATE … WHERE version = %s` para as seguintes —, sem a corrida "ler,
decidir, gravar".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Final, cast

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from axon_ai.assistants.api import Conflict, OverrideAction, OverrideSection
from axon_ai.assistants.domain.overrides import OverrideHistoryRecord, StoredOverride

_COLUMNS: Final = "assistant, section, payload, fingerprint, version, updated_by, updated_at"


def _record(row: Sequence[Any]) -> StoredOverride:
    assistant, section, payload, fingerprint, version, updated_by, updated_at = row
    return StoredOverride(
        assistant=assistant,
        section=cast("OverrideSection", section),
        payload=payload,
        fingerprint=fingerprint,
        version=version,
        updated_by=updated_by,
        updated_at=updated_at,
    )


class PostgresSystemOverrideStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def all(self) -> Sequence[StoredOverride]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_COLUMNS} FROM assistants.system_overrides ORDER BY assistant, section"
            )
            rows = await cursor.fetchall()
        return [_record(row) for row in rows]

    async def get(self, assistant: str) -> Sequence[StoredOverride]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_COLUMNS} FROM assistants.system_overrides WHERE assistant = %s ORDER BY section",
                (assistant,),
            )
            rows = await cursor.fetchall()
        return [_record(row) for row in rows]

    async def _current_version(self, connection: Any, assistant: str, section: str) -> int | None:
        cursor = await connection.execute(
            "SELECT version FROM assistants.system_overrides WHERE assistant = %s AND section = %s",
            (assistant, section),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else None

    async def put(self, record: StoredOverride, *, expected_version: int | None) -> StoredOverride:
        version = (expected_version or 0) + 1
        values = (
            Jsonb(dict(record.payload)),
            record.fingerprint,
            version,
            record.updated_by,
            record.updated_at,
        )
        async with self._pool.connection() as connection, connection.transaction():
            if expected_version is None:
                cursor = await connection.execute(
                    f"INSERT INTO assistants.system_overrides ({_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (assistant, section) DO NOTHING",
                    (record.assistant, record.section, *values),
                )
            else:
                cursor = await connection.execute(
                    "UPDATE assistants.system_overrides SET payload = %s, fingerprint = %s, version = %s, "
                    "updated_by = %s, updated_at = %s WHERE assistant = %s AND section = %s AND version = %s",
                    (*values, record.assistant, record.section, expected_version),
                )
            if cursor.rowcount != 1:
                current = await self._current_version(connection, record.assistant, record.section)
                raise Conflict("a sobreposição mudou desde a leitura", current_version=current)
            await self._log(
                connection,
                record.assistant,
                record.section,
                "saved",
                record.payload,
                version,
                record.updated_by,
                record.updated_at,
            )
        return StoredOverride(
            assistant=record.assistant,
            section=record.section,
            payload=record.payload,
            fingerprint=record.fingerprint,
            version=version,
            updated_by=record.updated_by,
            updated_at=record.updated_at,
        )

    async def delete(self, assistant: str, section: str, *, expected_version: int, actor: str, at: datetime) -> bool:
        async with self._pool.connection() as connection, connection.transaction():
            cursor = await connection.execute(
                "DELETE FROM assistants.system_overrides WHERE assistant = %s AND section = %s AND version = %s",
                (assistant, section, expected_version),
            )
            if cursor.rowcount != 1:
                current = await self._current_version(connection, assistant, section)
                if current is None:
                    return False
                raise Conflict("a sobreposição mudou desde a leitura", current_version=current)
            await self._log(connection, assistant, section, "discarded", None, expected_version, actor, at)
        return True

    @staticmethod
    async def _log(
        connection: Any,
        assistant: str,
        section: str,
        action: OverrideAction,
        payload: object,
        version: int,
        actor: str,
        at: datetime,
    ) -> None:
        await connection.execute(
            "INSERT INTO assistants.system_override_history (assistant, section, action, payload, version, actor, at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                assistant,
                section,
                action,
                Jsonb(dict(payload)) if isinstance(payload, Mapping) else None,
                version,
                actor,
                at,
            ),
        )

    async def history(self, assistant: str) -> Sequence[OverrideHistoryRecord]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT assistant, section, action, payload, version, actor, at "
                "FROM assistants.system_override_history WHERE assistant = %s ORDER BY id DESC",
                (assistant,),
            )
            rows = await cursor.fetchall()
        return [
            OverrideHistoryRecord(
                assistant=row[0],
                section=cast("OverrideSection", row[1]),
                action=cast("OverrideAction", row[2]),
                payload=row[3],
                version=row[4],
                actor=row[5],
                at=row[6],
            )
            for row in rows
        ]
