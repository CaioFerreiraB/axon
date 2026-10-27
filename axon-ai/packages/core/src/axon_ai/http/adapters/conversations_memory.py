"""`ConversationStore` em memória: perfis `memory` e `test`, e a referência da suíte de conformidade."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime

from axon_ai.http.domain.conversations import decode_cursor, encode_cursor
from axon_ai.http.ports import Conversation, ConversationPage, StoredMessage
from axon_ai_contracts import Attachment


class InMemoryConversationStore:
    """Conversas e mensagens em dicionários, sempre lidas no escopo do dono."""

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[StoredMessage]] = {}
        self._files: dict[str, dict[str, Attachment]] = {}

    async def create(self, conversation: Conversation) -> None:
        self._conversations[conversation.id] = conversation
        self._messages[conversation.id] = []
        self._files[conversation.id] = {}

    async def get(self, owner: str, conversation_id: str) -> Conversation | None:
        conversation = self._conversations.get(conversation_id)
        return conversation if conversation is not None and conversation.owner == owner else None

    async def messages(self, owner: str, conversation_id: str) -> Sequence[StoredMessage] | None:
        if await self.get(owner, conversation_id) is None:
            return None
        return tuple(self._messages[conversation_id])

    async def append(
        self,
        owner: str,
        conversation_id: str,
        messages: Sequence[StoredMessage],
        *,
        at: datetime,
        files: Sequence[Attachment] = (),
    ) -> bool:
        conversation = await self.get(owner, conversation_id)
        if conversation is None:
            return False
        self._messages[conversation_id].extend(messages)
        by_id = {item.id: item for item in files}
        for message in messages:
            for meta in message.attachments:
                self._files[conversation_id][meta.id] = by_id[meta.id]
        self._conversations[conversation_id] = dataclasses.replace(
            conversation, last_activity_at=at, message_count=conversation.message_count + len(messages)
        )
        return True

    async def attachment(self, owner: str, conversation_id: str, attachment_id: str) -> Attachment | None:
        if await self.get(owner, conversation_id) is None:
            return None
        return self._files[conversation_id].get(attachment_id)

    async def list(self, owner: str, *, limit: int, cursor: str | None) -> ConversationPage:
        items = sorted(
            (c for c in self._conversations.values() if c.owner == owner),
            key=lambda c: (c.last_activity_at, c.id),
            reverse=True,
        )
        if cursor is not None:
            after = decode_cursor(cursor)
            items = [c for c in items if (c.last_activity_at, c.id) < after]
        page = items[:limit]
        next_cursor = encode_cursor(page[-1].last_activity_at, page[-1].id) if len(items) > limit else None
        return ConversationPage(items=tuple(page), next_cursor=next_cursor)

    async def delete(self, owner: str, conversation_id: str) -> bool:
        if await self.get(owner, conversation_id) is None:
            return False
        del self._conversations[conversation_id]
        del self._messages[conversation_id]
        del self._files[conversation_id]
        return True

    async def delete_inactive(self, *, before: datetime) -> int:
        expired = [c.id for c in self._conversations.values() if c.last_activity_at < before]
        for conversation_id in expired:
            del self._conversations[conversation_id]
            del self._messages[conversation_id]
            del self._files[conversation_id]
        return len(expired)
