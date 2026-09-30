"""Regras de conversa (research R21): paginação e, no fluxo de chat, que mensagens entram e o que é gravado.

Puras. O armazenamento é da porta `ConversationStore`; aqui mora só o que decide, para que os dois adapters (memória e
Postgres) e o serviço digam a mesma coisa.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final, cast

from ai_core.graph.api import FinalEvent
from ai_core.http.domain.errors import InvalidRequest
from ai_core.http.domain.openai_chunks import FINISH_ERROR, finish_reason
from ai_core.http.domain.records import Conversation, StoredMessage
from ai_core_contracts import JSONValue, Message

DEFAULT_PAGE: Final = 20
MAX_PAGE: Final = 100


def encode_cursor(last_activity_at: datetime, conversation_id: str) -> str:
    """Cursor opaco da listagem: a posição (última atividade, id) do último item da página."""
    raw = f"{last_activity_at.isoformat()}|{conversation_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        instant, separator, conversation_id = raw.partition("|")
        at = datetime.fromisoformat(instant)
    except (binascii.Error, UnicodeDecodeError, ValueError) as error:
        raise InvalidRequest("cursor inválido", field="cursor") from error
    if not separator or not conversation_id or at.tzinfo is None:
        raise InvalidRequest("cursor inválido", field="cursor")
    return at, conversation_id


def page_size(raw: str | None) -> int:
    """`limit` da listagem: 1 a 100, default 20."""
    if raw is None:
        return DEFAULT_PAGE
    try:
        value = int(raw)
    except ValueError:
        raise InvalidRequest("limit precisa ser um inteiro", field="limit") from None
    if not 1 <= value <= MAX_PAGE:
        raise InvalidRequest(f"limit precisa estar entre 1 e {MAX_PAGE}", field="limit")
    return value


# --- fluxo de chat (research R21) ------------------------------------------------------------------------------------

USER: Final = "user"


def last_user_message(messages: Sequence[Message]) -> Message:
    """A última mensagem de usuário do pedido — o parser garante que existe ao menos uma."""
    for message in reversed(messages):
        if message["role"] == USER:
            return {"role": USER, "content": message["content"]}
    raise InvalidRequest("é preciso ao menos uma mensagem de papel 'user'", field="messages")


def execution_messages(history: Sequence[StoredMessage], requested: Sequence[Message]) -> tuple[Message, ...]:
    """Histórico armazenado + a última mensagem de usuário do pedido.

    O que o cliente manda como resposta anterior (papel `assistant` ou `tool`) é descartado: o histórico armazenado é a
    fonte de verdade, e uma resposta forjada nunca entra numa execução com id de conversa (SC-005).
    """
    stored: tuple[Message, ...] = tuple({"role": m.role, "content": m.content} for m in history)
    return (*stored, last_user_message(requested))


def exchange(user: Message, final: FinalEvent, *, request_id: str, at: datetime) -> tuple[StoredMessage, ...]:
    """A troca a gravar: a mensagem do usuário e a resposta, com citações e marcações. Execução que falhou não grava
    nada — o usuário tenta de novo sem deixar uma resposta parcial no histórico."""
    if finish_reason(final) == FINISH_ERROR:
        return ()
    return (
        StoredMessage(role="user", content=user["content"], at=at, request_id=request_id),
        StoredMessage(
            role="assistant",
            content=final.answer,
            at=at,
            request_id=request_id,
            citations=tuple(cast("JSONValue", dict(citation)) for citation in final.citations),
            flags=tuple(sorted(final.flags)),
        ),
    )


def conversation_json(conversation: Conversation, messages: Sequence[StoredMessage] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": conversation.id,
        "assistant": conversation.assistant,
        "model": conversation.model,
        "created_at": conversation.created_at.isoformat(),
        "last_activity_at": conversation.last_activity_at.isoformat(),
        "message_count": conversation.message_count,
    }
    if messages is not None:
        body["messages"] = [
            {
                "role": m.role,
                "content": m.content,
                "at": m.at.isoformat(),
                "request_id": m.request_id,
                "citations": list(m.citations),
                "flags": list(m.flags),
            }
            for m in messages
        ]
    return body
