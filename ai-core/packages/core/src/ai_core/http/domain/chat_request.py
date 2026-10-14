"""Leitura do corpo de chat completions: puro, sem I/O e sem framework HTTP.

Aqui mora a borda do princípio IV: campo que ampliaria capacidade é **rejeitado**, não ignorado — aceitar em silêncio
faria o cliente acreditar que suas tools seriam usadas. E aqui mora a FR-012: a API não aceita data de referência em
superfície nenhuma, porque execução de avaliação fixa a data em processo, pelo harness (ADR-013).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from ai_core.assistants.api import WIDENING_FIELDS
from ai_core.http.domain.errors import InvalidRequest
from ai_core_contracts import Message

CAPABILITY_FIELDS: Final = tuple(sorted(WIDENING_FIELDS))
"""Campos que ampliariam o que a execução pode fazer: a lista é da 003, a recusa é da borda (research R18)."""

REFERENCE_TIME_FIELDS: Final = ("reference_time", "reference_date", "as_of")
"""Nomes de data de referência recusados em qualquer superfície (FR-012)."""

IGNORED_SAMPLING_FIELDS: Final = ("temperature", "top_p", "max_tokens", "max_completion_tokens")
"""Aceitos e ignorados nesta fase; entram com os limites do Assistant na Fase 2."""

USER_ROLE: Final = "user"

STORE_HEADER: Final = "x-ai-core-store"
"""Cabeçalho do pedido efêmero (FR-023): `false`, sem id de conversa, executa sem criar nem gravar conversa."""

PROGRESS_HEADER: Final = "x-ai-core-progress"
"""Como o progresso aparece em streaming (FR-005a): `reasoning` (padrão) ou `status`, a timeline do Open WebUI."""

type ProgressMode = Literal["reasoning", "status"]


class ChatRequestInvalid(InvalidRequest):
    """Corpo recusado. A mensagem sempre nomeia o campo, para que o cliente saiba o que corrigir."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ChatRequest:
    """O que a API extrai do corpo e entrega ao serviço."""

    model: str
    messages: tuple[Message, ...]
    stream: bool
    conversation_id: str | None = None
    store: bool = True
    """`False` no pedido efêmero (FR-023): nenhuma conversa é criada nem gravada."""
    progress: ProgressMode = "reasoning"
    """`status` mostra o progresso como timeline de status do Open WebUI (FR-005a)."""


def parse(
    body: Mapping[str, Any], *, store_header: str | None = None, progress_header: str | None = None
) -> ChatRequest:
    """Valida o corpo no formato OpenAI (e os cabeçalhos `x-ai-core-store` e `x-ai-core-progress`) e devolve só o que a
    execução usa."""
    reject_forbidden(body)

    model = body.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ChatRequestInvalid("campo 'model' é obrigatório e não pode ser vazio", field="model")

    conversation_id = parse_conversation_id(body)
    return ChatRequest(
        model=model,
        messages=parse_messages(body.get("messages")),
        stream=parse_stream(body),
        conversation_id=conversation_id,
        store=parse_store(store_header, conversation_id),
        progress=parse_progress(progress_header),
    )


def parse_progress(value: str | None) -> ProgressMode:
    """O cabeçalho `x-ai-core-progress` (FR-005a, research R42): ausente ou `reasoning` é o FR-005; `status` é a
    timeline. Outro valor é recusado — aceitar em silêncio esconderia um erro de configuração da conexão."""
    if value is None:
        return "reasoning"
    normalized = value.strip().lower()
    if normalized == "reasoning":
        return "reasoning"
    if normalized == "status":
        return "status"
    raise ChatRequestInvalid(
        f"cabeçalho '{PROGRESS_HEADER}' aceita só 'reasoning' ou 'status': {value!r}",
        field=PROGRESS_HEADER,
        code="invalid_header",
    )


def parse_store(value: str | None, conversation_id: str | None) -> bool:
    """O cabeçalho `x-ai-core-store` (FR-023, research R37): ausente ou `true` grava; `false` sem id de conversa torna o
    pedido efêmero; `false` com id é contraditório — continuar uma conversa sem gravá-la — e é recusado."""
    if value is None:
        return True
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized != "false":
        raise ChatRequestInvalid(
            f"cabeçalho '{STORE_HEADER}' aceita só 'true' ou 'false': {value!r}",
            field=STORE_HEADER,
            code="invalid_header",
        )
    if conversation_id is not None:
        raise ChatRequestInvalid(
            f"cabeçalho '{STORE_HEADER}: false' não combina com 'conversation_id': continuar uma conversa a grava",
            field=STORE_HEADER,
            code="store_conflict",
        )
    return False


def parse_stream(body: Mapping[str, Any]) -> bool:
    stream = body.get("stream", False)
    if not isinstance(stream, bool):
        raise ChatRequestInvalid("campo 'stream' precisa ser booleano", field="stream")
    return stream


def parse_conversation_id(body: Mapping[str, Any]) -> str | None:
    """Continuação de conversa (US7). Na compat é campo extra do corpo, que os SDKs mandam por `extra_body`."""
    value = body.get("conversation_id")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ChatRequestInvalid("campo 'conversation_id' precisa ser um texto", field="conversation_id")
    return value


def reject_forbidden(body: Mapping[str, Any]) -> None:
    for field in CAPABILITY_FIELDS:
        if body.get(field) is not None:
            raise ChatRequestInvalid(
                f"campo '{field}' não é aceito: capacidades vêm do Assistant, e a requisição só pode restringir",
                field=field,
                code="widening_field",
            )
    for field in REFERENCE_TIME_FIELDS:
        if field in body:
            raise ChatRequestInvalid(
                f"campo '{field}' não é aceito em nenhuma superfície: a data de referência de uma avaliação é "
                f"fixada em processo, pelo harness",
                field=field,
                code="reference_time",
            )


def parse_messages(raw: Any) -> tuple[Message, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes) or not raw:
        raise ChatRequestInvalid("campo 'messages' é obrigatório e precisa de ao menos uma mensagem", field="messages")

    messages: list[Message] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ChatRequestInvalid(f"mensagem {index} precisa ser um objeto com 'role' e 'content'", field="messages")
        role, content = item.get("role"), item.get("content")
        if not isinstance(role, str) or not role.strip():
            raise ChatRequestInvalid(f"mensagem {index} precisa de 'role'", field="messages")
        if not isinstance(content, str):
            raise ChatRequestInvalid(f"mensagem {index} precisa de 'content' em texto", field="messages")
        messages.append({"role": role, "content": content})

    if not any(message["role"] == USER_ROLE and message["content"].strip() for message in messages):
        raise ChatRequestInvalid("é preciso ao menos uma mensagem de papel 'user' com conteúdo", field="messages")
    return tuple(messages)
