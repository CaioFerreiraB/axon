"""Teto de contexto do grant — estimativa determinística e omissão dos resultados mais antigos (FR-011, research R22).

Puro e sem tokenizador: `ceil(caracteres / 3) + 4` por mensagem sobrestima português e JSON, e é o que basta para um
teto que é proteção, não cobrança. A omissão troca o **conteúdo** de resultados de tool, do mais antigo para o mais
novo, por uma marca visível; a mensagem continua lá, e os passos acumulados no estado ficam intactos (FR-009, SC-005).
O corte de chunks por rank do `rag_first` (Fase 5) entra aqui, pela mesma regra: o que vale menos sai primeiro.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from typing import Final

from ai_core_contracts import ChatMessage

CHARS_PER_TOKEN: Final = 3
MESSAGE_OVERHEAD: Final = 4
OMITTED: Final = "[resultado omitido: teto de contexto]"

TOOL_ROLE: Final = "tool"


def _chars(message: ChatMessage) -> int:
    total = len(message.get("content") or "")
    for call in message.get("tool_calls", ()):
        total += len(call["name"]) + len(call["arguments"])
    return total


def estimate_tokens(messages: Sequence[ChatMessage]) -> int:
    return sum(ceil(_chars(message) / CHARS_PER_TOKEN) + MESSAGE_OVERHEAD for message in messages)


def exceeds(messages: Sequence[ChatMessage], ceiling: int | None) -> bool:
    """Sem teto declarado, nada excede."""
    return ceiling is not None and estimate_tokens(messages) > ceiling


@dataclass(frozen=True, slots=True, kw_only=True)
class Trimmed:
    messages: tuple[ChatMessage, ...]
    omitted: int
    overflow: bool
    """Ainda acima do teto depois de omitir todos os resultados — o histórico não é cortado nesta fase."""


def trim_results(messages: Sequence[ChatMessage], ceiling: int | None) -> Trimmed:
    """Omite resultados de tool, do mais antigo para o mais novo, até caber no teto."""
    current = list(messages)
    if ceiling is None:
        return Trimmed(messages=tuple(current), omitted=0, overflow=False)
    omitted = 0
    for index, message in enumerate(current):
        if not exceeds(current, ceiling):
            break
        if message["role"] == TOOL_ROLE:
            current[index] = {**message, "content": OMITTED}
            omitted += 1
    return Trimmed(messages=tuple(current), omitted=omitted, overflow=exceeds(current, ceiling))
