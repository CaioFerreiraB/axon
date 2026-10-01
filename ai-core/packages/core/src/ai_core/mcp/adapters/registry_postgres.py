"""`McpServerStore` em Postgres, no schema `mcp` (ADR-015; research R12).

O rascunho é serializado em JSON (`format: 1`); a forma do JSON é detalhe deste adapter — nenhum outro módulo a lê. A
unicidade de `(dono, alias)` é dos índices, não de uma leitura prévia. Datas entram como parâmetro, nunca `now()`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ai_core.mcp.api import McpServerDraft, SecurityPolicy
from ai_core.mcp.ports import StoredServer

FORMAT: Final = 1
_COLUMNS = "owner, alias, definition, created_at, updated_at"
_OWNER = "owner IS NOT DISTINCT FROM %s"


def _to_json(draft: McpServerDraft) -> dict[str, Any]:
    policy = draft.policy
    return {
        "format": FORMAT,
        "alias": draft.alias,
        "transport": draft.transport,
        "endpoint": draft.endpoint,
        "description": draft.description,
        "auth_type": draft.auth_type,
        "credential_ref": draft.credential_ref,
        "enabled": draft.enabled,
        "user_access": draft.user_access,
        "policy": {
            "allowed_tools": list(policy.allowed_tools),
            "write_tools": list(policy.write_tools),
            "timeout_ms": policy.timeout_ms,
            "max_response_bytes": policy.max_response_bytes,
        },
    }


def _from_json(data: Mapping[str, Any]) -> McpServerDraft:
    if data.get("format") != FORMAT:
        raise ValueError(f"formato de servidor desconhecido: {data.get('format')!r}")
    policy = data["policy"]
    return McpServerDraft(
        alias=data["alias"],
        transport=data["transport"],
        endpoint=data.get("endpoint"),
        description=data.get("description"),
        auth_type=data.get("auth_type", "none"),
        credential_ref=data.get("credential_ref"),
        enabled=data.get("enabled", True),
        user_access=data.get("user_access", False),
        policy=SecurityPolicy(
            allowed_tools=tuple(policy["allowed_tools"]),
            write_tools=tuple(policy.get("write_tools", ())),
            timeout_ms=policy["timeout_ms"],
            max_response_bytes=policy["max_response_bytes"],
        ),
    )


def _stored(row: Sequence[Any]) -> StoredServer:
    owner, _alias, definition, created_at, updated_at = row
    return StoredServer(owner=owner, draft=_from_json(definition), created_at=created_at, updated_at=updated_at)


class PostgresServerStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self, owner: str | None, alias: str) -> StoredServer | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_COLUMNS} FROM mcp.servers WHERE {_OWNER} AND alias = %s", (owner, alias)
            )
            row = await cursor.fetchone()
        return _stored(row) if row is not None else None

    async def list(self, owner: str | None) -> Sequence[StoredServer]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_COLUMNS} FROM mcp.servers WHERE {_OWNER} ORDER BY alias", (owner,)
            )
            rows = await cursor.fetchall()
        return [_stored(row) for row in rows]

    async def all(self) -> Sequence[StoredServer]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(f"SELECT {_COLUMNS} FROM mcp.servers ORDER BY owner NULLS FIRST, alias")
            rows = await cursor.fetchall()
        return [_stored(row) for row in rows]

    async def insert(self, record: StoredServer) -> bool:
        try:
            async with self._pool.connection() as connection:
                await connection.execute(
                    f"INSERT INTO mcp.servers ({_COLUMNS}) VALUES (%s, %s, %s, %s, %s)",
                    (record.owner, record.alias, Jsonb(_to_json(record.draft)), record.created_at, record.updated_at),
                )
        except UniqueViolation:
            return False
        return True

    async def replace(self, record: StoredServer) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"UPDATE mcp.servers SET definition = %s, updated_at = %s WHERE {_OWNER} AND alias = %s",
                (Jsonb(_to_json(record.draft)), record.updated_at, record.owner, record.alias),
            )
            return cursor.rowcount == 1

    async def delete(self, owner: str | None, alias: str) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(f"DELETE FROM mcp.servers WHERE {_OWNER} AND alias = %s", (owner, alias))
            return cursor.rowcount == 1
