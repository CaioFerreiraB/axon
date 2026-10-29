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

from axon_ai.graph.api import FinalEvent
from axon_ai.http.domain.charts import charts_table
from axon_ai.http.domain.errors import InvalidRequest
from axon_ai.http.domain.images import SENT, SHOWN, summary, with_markers
from axon_ai.http.domain.openai_chunks import FINISH_ERROR, finish_reason
from axon_ai.http.domain.records import Conversation, StoredAttachment, StoredMessage
from axon_ai_contracts import Attachment, JSONValue, Message

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
    """A última mensagem de usuário do pedido, com as imagens dela — o parser garante que existe ao menos uma."""
    for message in reversed(messages):
        if message["role"] == USER:
            images = tuple(message.get("attachments", ()))
            if images:
                return {"role": USER, "content": message["content"], "attachments": images}
            return {"role": USER, "content": message["content"]}
    raise InvalidRequest("é preciso ao menos uma mensagem de papel 'user'", field="messages")


def last_assistant(history: Sequence[StoredMessage]) -> StoredMessage | None:
    for message in reversed(history):
        if message.role == "assistant":
            return message
    return None


def execution_messages(
    history: Sequence[StoredMessage], requested: Sequence[Message], candidates: Sequence[Attachment] = ()
) -> tuple[Message, ...]:
    """Histórico armazenado + a última mensagem de usuário do pedido.

    O que o cliente manda como resposta anterior (papel `assistant` ou `tool`) é descartado: o histórico armazenado é a
    fonte de verdade, e uma resposta forjada nunca entra numa execução com id de conversa (SC-005). As imagens da última
    resposta, lidas do banco, voltam presas a ela: são as candidatas do turno (ADR-044, item 9).
    """
    last = last_assistant(history)
    stored: list[Message] = []
    for message in history:
        if message is last and candidates:
            stored.append({"role": message.role, "content": message.content, "attachments": tuple(candidates)})
        else:
            stored.append({"role": message.role, "content": message.content})
    return (*stored, last_user_message(requested))


def exchange(
    user: Message, final: FinalEvent, *, request_id: str, at: datetime
) -> tuple[tuple[StoredMessage, ...], tuple[Attachment, ...]]:
    """A troca a gravar e os bytes das imagens dela: a mensagem do usuário e a resposta, com citações, marcações e uma
    marca por imagem no texto — nunca o data URI (ADR-044, item 9). Execução que falhou não grava nada — o usuário
    tenta de novo sem deixar uma resposta parcial no histórico."""
    if finish_reason(final) == FINISH_ERROR:
        return (), ()
    sent = tuple(user.get("attachments", ()))
    records = (
        StoredMessage(
            role="user",
            content=with_markers(user["content"], sent, SENT),
            at=at,
            request_id=request_id,
            attachments=_stored(sent),
        ),
        StoredMessage(
            role="assistant",
            content=with_markers(_with_tables(final), final.attachments, SHOWN),
            at=at,
            request_id=request_id,
            citations=tuple(cast("JSONValue", dict(citation)) for citation in final.citations),
            flags=tuple(sorted(final.flags)),
            attachments=_stored(final.attachments),
        ),
    )
    return records, (*sent, *final.attachments)


def _with_tables(final: FinalEvent) -> str:
    """A resposta com a tabela de cada gráfico, como o cliente a recebeu: é o que o modelo lê no turno seguinte
    (ADR-052, item 5)."""
    tables = charts_table(final.charts)
    return final.answer + tables if final.answer else tables.lstrip("\n")


def _stored(images: Sequence[Attachment]) -> tuple[StoredAttachment, ...]:
    return tuple(
        StoredAttachment(id=item["id"], mime=item["mime"], size_bytes=item["size_bytes"]) for item in summary(images)
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
                "attachments": [{"id": a.id, "mime": a.mime, "size_bytes": a.size_bytes} for a in m.attachments],
            }
            for m in messages
        ]
    return body
