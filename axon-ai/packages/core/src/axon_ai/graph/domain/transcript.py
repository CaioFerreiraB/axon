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
from axon_ai.graph.domain.budget import RESULT_HEADER
from axon_ai.graph.domain.images import (
    CHARTS_INSTRUCTION,
    IMAGES_CAPABILITY,
    IMAGES_INSTRUCTION,
    VIEWED_NOTICE,
    candidates_text,
    gate_instruction,
    last_user_index,
    user_content,
)
from axon_ai.llm.api import ModelMessage
from axon_ai_contracts import Attachment, ChatToolCall, Message

INVALID_NOTICE: Final = "A ação anterior era inválida: {reason}. Responda com uma ação válida."

DATE_INSTRUCTION: Final = (
    "Data de referência: {weekday}, {date}, {time} ({zone}). Use-a para interpretar hoje, este mês, um mês ou dia "
    "sem ano e outros períodos relativos."
)
"""Sem ela, o modelo chuta o ano pela data de corte do treino e pede a período errado (R50)."""

NO_TOOLS_INSTRUCTION: Final = (
    "Nesta etapa você só escreve a resposta ao usuário, em texto: as ferramentas já foram usadas e não estão mais "
    "disponíveis. Nunca escreva chamadas de ferramenta, JSON de ação nem marcações como <tool_call>."
)
"""Na geração depois do loop: sem ela, um modelo que ainda queria agir escreve a chamada como texto — o filtro de
marcação a corta, e a resposta fica vazia (R54)."""

LIMIT_INSTRUCTION: Final = (
    "O limite de passos desta resposta foi atingido antes de terminar o que o usuário pediu. Responda com o que os "
    "resultados das ferramentas já trazem e diga com clareza o que ficou faltando — por exemplo, um gráfico ou uma "
    "consulta que não chegou a ser feita —, sugerindo pedir de novo de forma mais direta."
)
"""Na geração quando o loop foi cortado pelo limite de iterações (R54). Sem domínio (princípio I)."""

_WEEKDAYS: Final = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


def date_instruction(reference_time: datetime, zone: tzinfo) -> str:
    """A data de referência no fuso da instalação, por extenso."""
    local = reference_time.astimezone(zone)
    name = getattr(zone, "key", None) or local.tzname() or "UTC"
    return DATE_INSTRUCTION.format(
        weekday=_WEEKDAYS[local.weekday()], date=local.strftime("%d/%m/%Y"), time=local.strftime("%H:%M"), zone=name
    )


def repeats_view(image: str, steps: Sequence[Step]) -> bool:
    """A mesma imagem pedida de novo: a regra da ação repetida vale também para `view_image` (ADR-044, item 8)."""
    return any(isinstance(step, ViewStep) and step.image == image for step in steps)


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


@dataclass(frozen=True, slots=True, kw_only=True)
class ViewStep:
    """Uma imagem da resposta anterior marcada para a geração (ADR-044, item 8). O controller recebe só o aviso de que
    a marcou — a imagem não volta a ele; a geração a recebe na última mensagem do usuário."""

    iteration: int
    image: str


type Step = ToolStep | InvalidStep | ViewStep


def call_id(iteration: int) -> str:
    return f"call-{iteration}"


def _request(
    messages: Sequence[Message], *, send_own: bool = False, shown: Sequence[Attachment] = ()
) -> list[ModelMessage]:
    """A conversa ao modelo. Só a última mensagem do usuário leva imagem: as dele, se o papel as recebe, e as
    candidatas escolhidas (ADR-044, itens 5 e 8). As outras chegam com as marcas que a 008 já pôs no texto."""
    last = last_user_index(messages)
    request: list[ModelMessage] = []
    for index, message in enumerate(messages):
        if index == last:
            content = user_content(
                message["content"], tuple(message.get("attachments", ())), send_own=send_own, shown=shown
            )
            request.append({"role": message["role"], "content": content})
        else:
            request.append({"role": message["role"], "content": message["content"]})
    return request


def _arguments(call: ToolCall) -> str:
    return json.dumps(dict(call.arguments), ensure_ascii=False, sort_keys=True)


def _transcript(steps: Sequence[Step], *, notices: bool) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for step in steps:
        if isinstance(step, ToolStep):
            identifier = call_id(step.iteration)
            tool_call: ChatToolCall = {"id": identifier, "name": step.call.name, "arguments": _arguments(step.call)}
            messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
            messages.append({"role": "tool", "content": step.result.text, "tool_call_id": identifier})
        elif not notices:
            continue
        elif isinstance(step, ViewStep):
            messages.append({"role": "user", "content": VIEWED_NOTICE.format(id=step.image)})
        else:
            messages.append({"role": "user", "content": INVALID_NOTICE.format(reason=step.reason)})
    return messages


def _generation_transcript(steps: Sequence[Step]) -> list[ModelMessage]:
    """Os passos do loop como texto, um resultado por mensagem; o passo sintético do `rag_first` segue no formato
    nativo (R55).

    No formato nativo — `assistant` com `tool_calls` e a mensagem `tool` —, a geração vê uma conversa de chamadas de
    ferramenta e, sem ferramentas, continua o padrão escrevendo a chamada como texto (o glm-5.3-flash em produção, com o
    aviso de que elas acabaram e tudo). Em texto, ela lê os resultados e responde.
    """
    messages: list[ModelMessage] = []
    for step in steps:
        if not isinstance(step, ToolStep):
            continue
        if step.synthetic:
            messages.extend(_transcript((step,), notices=False))
            continue
        header = f"{RESULT_HEADER} {step.call.name}, chamada com {_arguments(step.call)}:"
        messages.append({"role": "user", "content": f"{header}\n{step.result.text}"})
    return messages


def controller_messages(
    tools: Sequence[CatalogTool],
    messages: Sequence[Message],
    steps: Sequence[Step],
    *,
    today: str | None = None,
    images: Sequence[str] = (),
    send_own: bool = False,
) -> list[ModelMessage]:
    """Sistema (instrução, data de referência, catálogo, os ids das imagens candidatas, cerca), a conversa e a
    transcrição — com os avisos de ação inválida e de imagem marcada.

    Sem prompts de pack: o controller escolhe tool; a voz do pack é da geração (tabela "Nós finos" do `design.md`). A
    imagem do usuário só vai se o controller declara `vision` (`send_own`); das candidatas, só os ids (ADR-044).
    """
    head = CONTROLLER_INSTRUCTION if today is None else f"{CONTROLLER_INSTRUCTION}\n\n{today}"
    parts = [head, catalog_text(tools)]
    if images:
        parts.append(candidates_text(images))
    system = "\n\n".join([*parts, FENCE_INSTRUCTION])
    return [
        {"role": "system", "content": system},
        *_request(messages, send_own=send_own),
        *_transcript(steps, notices=True),
    ]


def gate_messages(messages: Sequence[Message], images: Sequence[str], *, send_own: bool) -> list[ModelMessage]:
    """A etapa `image_gate`: o pedido de escolha com os ids candidatos e a conversa — a imagem do usuário só se o
    controller declara `vision`, e das candidatas só os ids (ADR-044, item 8)."""
    return [{"role": "system", "content": gate_instruction(images)}, *_request(messages, send_own=send_own)]


def generation_messages(
    prompts: Sequence[str],
    messages: Sequence[Message],
    steps: Sequence[Step],
    *,
    today: str | None = None,
    send_own: bool = False,
    shown: Sequence[Attachment] = (),
    tools: bool = False,
    truncated: bool = False,
) -> list[ModelMessage]:
    """Prompts de pack, a data de referência (no `agentic`), a cerca (se houver resultado) e o aviso das imagens que o
    usuário vê (se uma tool devolveu imagem; sem imagem, mas com tools na execução — `tools` —, a nota de que a
    plataforma as mostra), a conversa e a transcrição — sem os avisos de ação inválida.

    Sem passos, sem data e sem imagem, é exatamente o que o `chat` da Fase 1 envia. A última mensagem do usuário leva
    as imagens dele (`send_own`) e as candidatas escolhidas (`shown`), cada uma com a marca de onde veio (ADR-044).
    """
    system: list[ModelMessage] = [{"role": "system", "content": prompt} for prompt in prompts]
    if today is not None:
        system.append({"role": "system", "content": today})
    executed = [step for step in steps if isinstance(step, ToolStep)]
    if executed:
        system.append({"role": "system", "content": FENCE_INSTRUCTION})
    if any(step.result.attachments for step in executed):
        system.append({"role": "system", "content": IMAGES_INSTRUCTION})
    elif tools:
        system.append({"role": "system", "content": IMAGES_CAPABILITY})
    if any(step.result.charts for step in executed):
        system.append({"role": "system", "content": CHARTS_INSTRUCTION})
    if tools:
        system.append({"role": "system", "content": NO_TOOLS_INSTRUCTION})
    if truncated:
        system.append({"role": "system", "content": LIMIT_INSTRUCTION})
    return [*system, *_request(messages, send_own=send_own, shown=shown), *_generation_transcript(steps)]
