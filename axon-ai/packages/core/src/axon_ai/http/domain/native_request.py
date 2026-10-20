"""Requisição nativa (US3, research R17): nomeia o Assistant e, no máximo, restringe o modelo. Estrita de propósito.

A compat tolera campos da OpenAI que ignora; aqui qualquer campo desconhecido é recusado, para que a interface diga
com todas as letras o que a requisição pode fazer (princípio IV). A resposta é a mesma da compat.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from axon_ai.http.domain.chat_request import (
    ChatRequest,
    ChatRequestInvalid,
    parse_conversation_id,
    parse_messages,
    parse_progress,
    parse_store,
    parse_stream,
    reject_forbidden,
)

NATIVE_FIELDS: Final = frozenset({"assistant", "model", "messages", "stream", "conversation_id"})


def parse_native(
    body: Mapping[str, Any], *, store_header: str | None = None, progress_header: str | None = None
) -> ChatRequest:
    reject_forbidden(body)
    for field in sorted(str(key) for key in body if key not in NATIVE_FIELDS):
        raise ChatRequestInvalid(f"campo '{field}' não é aceito na requisição nativa", field=field)

    assistant = body.get("assistant")
    if not isinstance(assistant, str) or not assistant.strip() or "/" in assistant:
        raise ChatRequestInvalid("campo 'assistant' é obrigatório e é só o nome do Assistant", field="assistant")
    model = body.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ChatRequestInvalid("campo 'model' precisa ser um texto", field="model")

    conversation_id = parse_conversation_id(body)
    return ChatRequest(
        model=assistant if model is None else f"{assistant}/{model}",
        messages=parse_messages(body.get("messages")),
        stream=parse_stream(body),
        conversation_id=conversation_id,
        store=parse_store(store_header, conversation_id),
        progress=parse_progress(progress_header),
    )
