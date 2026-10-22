"""Mensagens enviadas ao controller e à geração — puras (research R19).

A transcrição do loop usa o formato nativo de tool do contrato 001: por tool executada, uma mensagem `assistant` com
`tool_calls` e uma mensagem `tool` com o texto **cercado** pelo gateway. Todo provider-alvo tem um lugar de menor
autoridade para saída de tool; pôr conteúdo externo no papel `user` lhe daria a autoridade do usuário (princípio VI).
A instrução da cerca (`FENCE_INSTRUCTION`, 004) vai no texto de sistema, sem alteração.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Final

from axon_ai.capabilities.api import FENCE_INSTRUCTION, CatalogTool, FencedToolResult, ToolCall
from axon_ai.graph.domain.actions import CONTROLLER_INSTRUCTION, catalog_text
from axon_ai_contracts import ChatMessage, ChatToolCall, Message

INVALID_NOTICE: Final = "A ação anterior era inválida: {reason}. Responda com uma ação válida."

DATE_INSTRUCTION: Final = (
    "Data de referência: {weekday}, {date}, {time} ({zone}). Use-a para interpretar hoje, este mês, um mês ou dia "
    "sem ano e outros períodos relativos."
)
"""Sem ela, o modelo chuta o ano pela data de corte do treino e pede a período errado (R50)."""

_WEEKDAYS: Final = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


def date_instruction(reference_time: datetime, zone: tzinfo) -> str:
    """A data de referência no fuso da instalação, por extenso."""
    local = reference_time.astimezone(zone)
    name = getattr(zone, "key", None) or local.tzname() or "UTC"
    return DATE_INSTRUCTION.format(
        weekday=_WEEKDAYS[local.weekday()], date=local.strftime("%d/%m/%Y"), time=local.strftime("%H:%M"), zone=name
    )


def repeats(call: ToolCall, steps: Sequence[Step]) -> bool:
    """O controller pediu de novo uma tool já executada com os mesmos argumentos (R50): o resultado está na
    transcrição, e repetir só gasta iteração."""
    wanted = (call.name, _arguments(call))
    return any(
        isinstance(step, ToolStep) and not step.synthetic and (step.call.name, _arguments(step.call)) == wanted
        for step in steps
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolStep:
    """Uma tool executada: o pedido do controller e o resultado como o gateway o devolveu (cercado)."""

    iteration: int
    call: ToolCall
    result: FencedToolResult
    synthetic: bool = False
    """O passo que o portão do `rag_first` grava com os trechos já recuperados (R41): entra na geração como um passo
    executado, mas a projeção não soma os chunks dele em `retrieved` — já estão entre os candidatos (R43)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidStep:
    """Uma ação inválida, com o motivo escrito pelo motor — nunca a saída do modelo (R18)."""

    iteration: int
    reason: str


type Step = ToolStep | InvalidStep


def call_id(iteration: int) -> str:
    return f"call-{iteration}"


def _request(messages: Sequence[Message]) -> list[ChatMessage]:
    return [{"role": message["role"], "content": message["content"]} for message in messages]


def _arguments(call: ToolCall) -> str:
    return json.dumps(dict(call.arguments), ensure_ascii=False, sort_keys=True)


def _transcript(steps: Sequence[Step], *, notices: bool) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for step in steps:
        if isinstance(step, ToolStep):
            identifier = call_id(step.iteration)
            tool_call: ChatToolCall = {"id": identifier, "name": step.call.name, "arguments": _arguments(step.call)}
            messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
            messages.append({"role": "tool", "content": step.result.text, "tool_call_id": identifier})
        elif notices:
            messages.append({"role": "user", "content": INVALID_NOTICE.format(reason=step.reason)})
    return messages


def controller_messages(
    tools: Sequence[CatalogTool],
    messages: Sequence[Message],
    steps: Sequence[Step],
    *,
    today: str | None = None,
) -> list[ChatMessage]:
    """Sistema (instrução, data de referência, catálogo, cerca), a conversa e a transcrição — com os avisos de ação
    inválida.

    Sem prompts de pack: o controller escolhe tool; a voz do pack é da geração (tabela "Nós finos" do `design.md`).
    """
    head = CONTROLLER_INSTRUCTION if today is None else f"{CONTROLLER_INSTRUCTION}\n\n{today}"
    system = f"{head}\n\n{catalog_text(tools)}\n\n{FENCE_INSTRUCTION}"
    return [{"role": "system", "content": system}, *_request(messages), *_transcript(steps, notices=True)]


def generation_messages(
    prompts: Sequence[str],
    messages: Sequence[Message],
    steps: Sequence[Step],
    *,
    today: str | None = None,
) -> list[ChatMessage]:
    """Prompts de pack, a data de referência (no `agentic`), a cerca (se houver resultado), a conversa e a transcrição
    — sem os avisos de ação inválida.

    Sem passos e sem data, é exatamente o que o `chat` da Fase 1 envia.
    """
    system: list[ChatMessage] = [{"role": "system", "content": prompt} for prompt in prompts]
    if today is not None:
        system.append({"role": "system", "content": today})
    if any(isinstance(step, ToolStep) for step in steps):
        system.append({"role": "system", "content": FENCE_INSTRUCTION})
    return [*system, *_request(messages), *_transcript(steps, notices=False)]
