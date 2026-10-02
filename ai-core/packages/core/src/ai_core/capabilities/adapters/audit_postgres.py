"""`AuditLog` em Postgres, no schema `capabilities` (ADR-015; contracts/audit.md).

Datas entram como parâmetro, nunca `now()` no SQL (ADR-013). Os argumentos vão em `jsonb` — chegam congelados do
gateway e viram JSON simples aqui.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ai_core.capabilities.api import AuditEntry, AuditFilter, AuditRecord, AuditStatus

_COLUMNS = "id, request_id, principal, assistant, tool, kind, arguments, status, result, started_at, finished_at"


def _plain(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    return value


def _record(row: Sequence[Any]) -> AuditRecord:
    record_id, request_id, principal, assistant, tool, kind, arguments, status, result, started, finished = row
    return AuditRecord(
        id=str(record_id),
        request_id=request_id,
        principal=principal,
        assistant=assistant,
        tool=tool,
        kind=kind,
        arguments=arguments,
        status=status,
        result=result,
        started_at=started,
        finished_at=finished,
    )


class PostgresAuditLog:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def begin(self, entry: AuditEntry) -> str:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "INSERT INTO capabilities.audit "
                "(request_id, principal, assistant, tool, kind, arguments, status, started_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'started', %s) RETURNING id",
                (
                    entry.request_id,
                    entry.principal,
                    entry.assistant,
                    entry.tool,
                    entry.kind,
                    Jsonb(_plain(entry.arguments)),
                    entry.started_at,
                ),
            )
            row = await cursor.fetchone()
        assert row is not None
        return str(row[0])

    async def finish(self, record_id: str, *, status: AuditStatus, result: str, at: datetime) -> None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "UPDATE capabilities.audit SET status = %s, result = %s, finished_at = %s WHERE id = %s",
                (status, result, at, int(record_id)),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"registro de auditoria '{record_id}' não existe")

    async def query(self, filter: AuditFilter) -> Sequence[AuditRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (("principal", filter.principal), ("assistant", filter.assistant), ("tool", filter.tool)):
            if value is not None:
                clauses.append(f"{column} = %s")
                params.append(value)
        if filter.since is not None:
            clauses.append("started_at >= %s")
            params.append(filter.since)
        if filter.until is not None:
            clauses.append("started_at <= %s")
            params.append(filter.until)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(filter.limit)
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_COLUMNS} FROM capabilities.audit {where} ORDER BY started_at DESC, id DESC LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return [_record(row) for row in rows]
