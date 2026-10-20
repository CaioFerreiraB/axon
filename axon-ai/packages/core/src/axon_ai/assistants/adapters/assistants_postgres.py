"""`UserAssistantStore` em Postgres, no schema `assistants` (ADR-015).

O rascunho é serializado em JSON (`format: 1`), com os modelos como `provider/modelo` — o mesmo texto do
`assistants.yaml`. A forma do JSON é detalhe deste adapter: nenhum outro módulo a lê.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from axon_ai.assistants.api import DraftLimits, UserAssistantDraft
from axon_ai.assistants.ports import StoredUserAssistant
from axon_ai.llm.api import ModelRef, ModelRole

FORMAT: Final = 1
_COLUMNS = "owner, definition, created_at, updated_at"


def _to_json(draft: UserAssistantDraft) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "name": draft.name,
        "description": draft.description,
        "flow": draft.flow,
        "packs": list(draft.packs),
        "mcp": list(draft.mcp),
        "collections": list(draft.collections),
        "models": {role: str(ref) for role, ref in draft.models.items()},
        "limits": {
            "rpm": draft.limits.rpm,
            "max_iterations": draft.limits.max_iterations,
            "max_context_tokens": draft.limits.max_context_tokens,
        },
        "allowed_tools": list(draft.allowed_tools) if draft.allowed_tools is not None else None,
        "write_tools": list(draft.write_tools),
    }


def _from_json(data: Mapping[str, Any]) -> UserAssistantDraft:
    if data.get("format") != FORMAT:
        raise ValueError(f"formato de rascunho desconhecido: {data.get('format')!r}")
    allowed = data.get("allowed_tools")
    return UserAssistantDraft(
        name=data["name"],
        description=data.get("description"),
        flow=data.get("flow"),
        packs=tuple(data.get("packs", ())),
        mcp=tuple(data.get("mcp", ())),
        collections=tuple(data.get("collections", ())),
        models={cast("ModelRole", role): ModelRef.parse(ref) for role, ref in data["models"].items()},
        limits=DraftLimits(**data.get("limits", {})),
        allowed_tools=tuple(allowed) if allowed is not None else None,
        write_tools=tuple(data.get("write_tools", ())),
    )


def _stored(row: Sequence[Any]) -> StoredUserAssistant:
    owner, definition, created_at, updated_at = row
    return StoredUserAssistant(owner=owner, draft=_from_json(definition), created_at=created_at, updated_at=updated_at)


class PostgresUserAssistantStore:
    """Assistants de usuário por (dono, nome). Unicidade pela chave primária, não por leitura prévia."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self, owner: str, name: str) -> StoredUserAssistant | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_COLUMNS} FROM assistants.user_assistants WHERE owner = %s AND name = %s", (owner, name)
            )
            row = await cursor.fetchone()
        return _stored(row) if row is not None else None

    async def list(self, owner: str) -> Sequence[StoredUserAssistant]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_COLUMNS} FROM assistants.user_assistants WHERE owner = %s ORDER BY name", (owner,)
            )
            rows = await cursor.fetchall()
        return [_stored(row) for row in rows]

    async def all(self) -> Sequence[StoredUserAssistant]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(f"SELECT {_COLUMNS} FROM assistants.user_assistants ORDER BY owner, name")
            rows = await cursor.fetchall()
        return [_stored(row) for row in rows]

    async def insert(self, record: StoredUserAssistant) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "INSERT INTO assistants.user_assistants (owner, name, definition, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (owner, name) DO NOTHING RETURNING 1",
                (record.owner, record.name, Jsonb(_to_json(record.draft)), record.created_at, record.updated_at),
            )
            return await cursor.fetchone() is not None

    async def replace(self, record: StoredUserAssistant) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "UPDATE assistants.user_assistants SET definition = %s, created_at = %s, updated_at = %s "
                "WHERE owner = %s AND name = %s RETURNING 1",
                (Jsonb(_to_json(record.draft)), record.created_at, record.updated_at, record.owner, record.name),
            )
            return await cursor.fetchone() is not None

    async def delete(self, owner: str, name: str) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "DELETE FROM assistants.user_assistants WHERE owner = %s AND name = %s RETURNING 1", (owner, name)
            )
            return await cursor.fetchone() is not None
