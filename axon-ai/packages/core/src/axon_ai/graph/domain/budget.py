"""Teto de contexto do grant — estimativa determinística e omissão dos resultados mais antigos (FR-011, research R22).

Puro e sem tokenizador: `ceil(caracteres / 3) + 4` por mensagem sobrestima português e JSON, e é o que basta para um
teto que é proteção, não cobrança. No `agentic`, a omissão troca o **conteúdo** de resultados de tool, do mais antigo
para o mais novo, por uma marca visível; a mensagem continua lá, e os passos acumulados no estado ficam intactos
(FR-009, SC-005). No `rag_first` (Fase 5, R42), `fit_chunks` tira os trechos de menor posição até caber — a mesma regra:
o que vale menos sai primeiro, e nenhum trecho é cortado no meio (quebraria a citação). Uma imagem enviada ao modelo
conta um custo fixo (`IMAGE_TOKENS`, ADR-044), e nenhuma regra a tira: quem decidiu enviá-la foi a pergunta.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import ceil
from typing import Final

from axon_ai.graph.domain.images import IMAGE_TOKENS
from axon_ai.llm.api import ModelMessage

CHARS_PER_TOKEN: Final = 3
MESSAGE_OVERHEAD: Final = 4
OMITTED: Final = "[resultado omitido: teto de contexto]"

TOOL_ROLE: Final = "tool"

RESULT_HEADER: Final = "Resultado da ferramenta"
"""Começo da mensagem com o resultado de uma tool do loop quando ele vai à geração como texto (R55): o corte por
teto a reconhece como resultado, como a mensagem de papel `tool`."""


def is_tool_result(message: ModelMessage) -> bool:
    """Resultado de tool, no formato nativo (papel `tool`) ou em texto (a mensagem que começa com `RESULT_HEADER`)."""
    if message["role"] == TOOL_ROLE:
        return True
    content = message.get("content")
    return message["role"] == "user" and isinstance(content, str) and content.startswith(RESULT_HEADER)


def _chars(message: ModelMessage) -> int:
    content = message.get("content")
    if content is None or isinstance(content, str):
        total = len(content or "")
    else:
        total = sum(len(part["text"]) for part in content if part["type"] == "text")
    for call in message.get("tool_calls", ()):
        total += len(call["name"]) + len(call["arguments"])
    return total


def _images(message: ModelMessage) -> int:
    content = message.get("content")
    if content is None or isinstance(content, str):
        return 0
    return sum(part["type"] == "image_url" for part in content)


def estimate_tokens(messages: Sequence[ModelMessage]) -> int:
    """Cada imagem enviada custa `IMAGE_TOKENS`, fixo (ADR-044): o tamanho do data URI não diz nada do custo real."""
    return sum(
        ceil(_chars(message) / CHARS_PER_TOKEN) + MESSAGE_OVERHEAD + IMAGE_TOKENS * _images(message)
        for message in messages
    )


def exceeds(messages: Sequence[ModelMessage], ceiling: int | None) -> bool:
    """Sem teto declarado, nada excede."""
    return ceiling is not None and estimate_tokens(messages) > ceiling


@dataclass(frozen=True, slots=True, kw_only=True)
class Trimmed:
    messages: tuple[ModelMessage, ...]
    omitted: int
    overflow: bool
    """Ainda acima do teto depois de omitir todos os resultados — o histórico não é cortado nesta fase."""


def trim_results(messages: Sequence[ModelMessage], ceiling: int | None) -> Trimmed:
    """Omite resultados de tool, do mais antigo para o mais novo, até caber no teto."""
    current = list(messages)
    if ceiling is None:
        return Trimmed(messages=tuple(current), omitted=0, overflow=False)
    omitted = 0
    for index, message in enumerate(current):
        if not exceeds(current, ceiling):
            break
        if is_tool_result(message):
            current[index] = {**message, "content": _omitted(message)}
            omitted += 1
    return Trimmed(messages=tuple(current), omitted=omitted, overflow=exceeds(current, ceiling))


def _omitted(message: ModelMessage) -> str:
    """No resultado em texto, a linha do cabeçalho (qual tool, com que argumentos) fica; o resto vira a marca."""
    if message["role"] == TOOL_ROLE:
        return OMITTED
    header = str(message.get("content")).split("\n", 1)[0]
    return f"{header}\n{OMITTED}"


@dataclass(frozen=True, slots=True, kw_only=True)
class Fitted[T]:
    items: tuple[T, ...]
    dropped: int
    overflow: bool
    """Nem sem nenhum item cabe — a geração segue e registra (FR-011)."""


def fit_chunks[T](
    items: Sequence[T], build: Callable[[Sequence[T]], Sequence[ModelMessage]], ceiling: int | None
) -> Fitted[T]:
    """Tira itens do **fim** (menor posição) até `build(prefixo)` caber no teto; nunca reordena.

    `build` monta as mensagens da geração com os itens que ficam — quem chama sabe como cada item vira mensagem.
    """
    if ceiling is None:
        return Fitted(items=tuple(items), dropped=0, overflow=False)
    for kept in range(len(items), -1, -1):
        if not exceeds(build(items[:kept]), ceiling):
            return Fitted(items=tuple(items[:kept]), dropped=len(items) - kept, overflow=False)
    return Fitted(items=(), dropped=len(items), overflow=True)
