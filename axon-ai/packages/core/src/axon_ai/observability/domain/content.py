"""O conteúdo opcional (ADR-034, research R29): o `model_exchange` redigido e cortado antes de sair do processo.

Puro. A redação é a mesma das credenciais do trace (FR-002) — cobre credenciais, não dados pessoais: é o que a console
avisa antes de ligar a captura. Cada mensagem e a saída são cortadas em 16 KiB, com marca.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from axon_ai.observability.api import ModelExchange, TraceRecord
from axon_ai.observability.domain.redaction import redact_text
from axon_ai_contracts import JSONValue

CONTENT_MAX: Final = 16 * 1024
"""Caracteres por mensagem e na saída; o excedente vira a marca de truncado."""

EXCHANGE_TYPE: Final = "model_exchange"


def redact_content(text: str) -> str:
    return redact_text(text, limit=CONTENT_MAX)


def exchange_record(event: ModelExchange, at: datetime) -> TraceRecord:
    """O registro do `model_exchange`, já redigido e cortado. Só vai a destinos que aceitam conteúdo."""
    messages: list[JSONValue] = [
        {"role": message.role, "content": redact_content(message.content)} for message in event.messages
    ]
    return TraceRecord(
        at=at,
        type=EXCHANGE_TYPE,
        request_id=event.request_id,
        attributes={
            "role": event.role,
            "provider": event.provider,
            "model": event.model,
            "messages": messages,
            "output": redact_content(event.output),
        },
    )
