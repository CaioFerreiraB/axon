"""`ConversationStore` em Postgres, no schema `http` (ADR-015, research R22).

Toda consulta é no escopo do dono. A gravação de uma troca trava a linha da conversa (`FOR UPDATE`), para que a
numeração das mensagens e a contagem não corram entre duas execuções da mesma conversa, e devolve `False` se a
conversa sumiu — a exclusão prevalece (FR-018).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ai_core.http.domain.conversations import decode_cursor, encode_cursor
from ai_core.http.ports import Conversation, ConversationPage, MessageRole, StoredMessage

_CONVERSATION = "id, owner, assistant, model, created_at, last_activity_at, message_count"


def _conversation(row: Sequence[Any]) -> Conversation:
    cid, owner, assistant, model, created_at, last_activity_at, message_count = row
    return Conversation(
        id=cid,
        owner=owner,
        assistant=assistant,
        model=model,
        created_at=created_at,
        last_activity_at=last_activity_at,
        message_count=message_count,
    )


class PostgresConversationStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create(self, conversation: Conversation) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                f"INSERT INTO http.conversations ({_CONVERSATION}) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    conversation.id,
                    conversation.owner,
                    conversation.assistant,
                    conversation.model,
                    conversation.created_at,
                    conversation.last_activity_at,
                    conversation.message_count,
                ),
            )

    async def get(self, owner: str, conversation_id: str) -> Conversation | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_CONVERSATION} FROM http.conversations WHERE owner = %s AND id = %s", (owner, conversation_id)
            )
            row = await cursor.fetchone()
        return _conversation(row) if row is not None else None

    async def messages(self, owner: str, conversation_id: str) -> Sequence[StoredMessage] | None:
        async with self._pool.connection() as connection:
            owned = await connection.execute(
                "SELECT 1 FROM http.conversations WHERE owner = %s AND id = %s", (owner, conversation_id)
            )
            if await owned.fetchone() is None:
                return None
            cursor = await connection.execute(
                "SELECT role, content, at, request_id, citations, flags FROM http.messages "
                "WHERE conversation_id = %s ORDER BY seq",
                (conversation_id,),
            )
            rows = await cursor.fetchall()
        return tuple(
            StoredMessage(
                role=cast("MessageRole", role),
                content=content,
                at=at,
                request_id=request_id,
                citations=tuple(citations),
                flags=tuple(flags),
            )
            for role, content, at, request_id, citations, flags in rows
        )

    async def append(
        self, owner: str, conversation_id: str, messages: Sequence[StoredMessage], *, at: datetime
    ) -> bool:
        async with self._pool.connection() as connection, connection.transaction():
            cursor = await connection.execute(
                "SELECT message_count FROM http.conversations WHERE owner = %s AND id = %s FOR UPDATE",
                (owner, conversation_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return False
            count = int(row[0])
            for offset, message in enumerate(messages):
                await connection.execute(
                    "INSERT INTO http.messages (conversation_id, seq, role, content, at, request_id, citations, flags) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        conversation_id,
                        count + offset,
                        message.role,
                        message.content,
                        message.at,
                        message.request_id,
                        Jsonb(list(message.citations)),
                        list(message.flags),
                    ),
                )
            await connection.execute(
                "UPDATE http.conversations SET message_count = %s, last_activity_at = %s WHERE id = %s",
                (count + len(messages), at, conversation_id),
            )
        return True

    async def list(self, owner: str, *, limit: int, cursor: str | None) -> ConversationPage:
        params: list[Any] = [owner]
        after = ""
        if cursor is not None:
            at, cid = decode_cursor(cursor)
            after = "AND (last_activity_at, id) < (%s, %s) "
            params += [at, cid]
        params.append(limit + 1)
        async with self._pool.connection() as connection:
            result = await connection.execute(
                f"SELECT {_CONVERSATION} FROM http.conversations WHERE owner = %s {after}"
                "ORDER BY last_activity_at DESC, id DESC LIMIT %s",
                params,
            )
            rows = await result.fetchall()
        items = [_conversation(row) for row in rows]
        page = items[:limit]
        next_cursor = encode_cursor(page[-1].last_activity_at, page[-1].id) if len(items) > limit else None
        return ConversationPage(items=tuple(page), next_cursor=next_cursor)

    async def delete(self, owner: str, conversation_id: str) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "DELETE FROM http.conversations WHERE owner = %s AND id = %s RETURNING 1", (owner, conversation_id)
            )
            return await cursor.fetchone() is not None

    async def delete_inactive(self, *, before: datetime) -> int:
        async with self._pool.connection() as connection:
            cursor = await connection.execute("DELETE FROM http.conversations WHERE last_activity_at < %s", (before,))
            return cursor.rowcount
