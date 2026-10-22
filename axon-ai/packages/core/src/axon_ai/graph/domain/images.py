"""Imagens na execução: quem as vê e quando — puro, sem I/O (ADR-044, itens 4, 5 e 8; research R51).

Três origens, três regras:

- **A imagem da última mensagem do usuário** é a pergunta: vai à geração sem decisão nenhuma (a 008 já recusou o pedido
  com 400 se o papel `generation` não tem `vision`) e ao controller só se ele também declara `vision`.
- **As imagens da última mensagem do assistente** são candidatas: só vão à geração se a pergunta for sobre elas. Quem
  decide é o controller — no loop, pela ação `view_image`; no `chat` e no `rag_first` coberto, numa etapa própria
  (`image_gate`). Sem controller, vão todas. Sem `vision` na geração, não há candidata.
- **As imagens que as tools devolvem neste turno** chegam ao usuário e não ao modelo: ele vê a marca da 004.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from axon_ai.llm.api import ContentPart, image_part
from axon_ai_contracts import Attachment, Message

USER_ROLE: Final = "user"
ASSISTANT_ROLE: Final = "assistant"

SENT_MARKER: Final = "[imagem {id} enviada pelo usuário]"
"""A imagem do usuário que o modelo não recebe (controller sem `vision`): ele sabe que ela existe."""

SHOWN_MARKER: Final = "[imagem {id} mostrada ao usuário]"
"""A marca que acompanha uma candidata escolhida na mensagem à geração: diz de onde ela veio (ADR-044, item 8)."""

IMAGES_INSTRUCTION: Final = (
    "As imagens marcadas no formato [imagem <id> mostrada ao usuário…] aparecem para o usuário junto da sua resposta. "
    "Não diga que não consegue mostrá-las nem que não tem acesso a elas: fale delas pelo que os resultados das "
    "ferramentas dizem."
)
"""Texto fixo do core, junto da `FENCE_INSTRUCTION`, na geração do turno em que uma tool devolveu imagem (item 4)."""

CANDIDATES_TEXT: Final = (
    "Imagens mostradas ao usuário na resposta anterior: {ids}. Se a última mensagem do usuário for sobre uma delas, "
    'responda {{"action": "view_image", "id": "<id>"}} para que a resposta possa vê-la; uma por vez.'
)
"""Só os ids vão ao controller do loop — a imagem não volta a ele (item 8)."""

VIEWED_NOTICE: Final = "A imagem {id} foi marcada para a resposta."

GATE_INSTRUCTION: Final = (
    "Decida se a última mensagem do usuário pergunta sobre alguma das imagens mostradas a ele na resposta anterior: "
    "{ids}. Responda apenas com um objeto JSON, sem texto fora dele: "
    '{{"view": ["<id>", ...]}} com os ids das imagens de que a resposta precisa, ou {{"view": []}} se nenhuma.'
)
"""Sistema da etapa `image_gate`. Sem domínio (princípio I)."""

GATE_SCHEMA_NAME: Final = "image_choice"

IMAGE_TOKENS: Final = 1_000
"""Custo fixo estimado de uma imagem enviada ao modelo, no teto de contexto (FR-011; ADR-044, Consequências).
Provisório: a calibrar com o provider, como os números do `rag_first` (princípio X)."""


def unique(attachments: Sequence[Attachment]) -> tuple[Attachment, ...]:
    """Na ordem, sem repetir `id` — a mesma imagem duas vezes é uma só (item 1)."""
    first: dict[str, Attachment] = {}
    for item in attachments:
        first.setdefault(item.id, item)
    return tuple(first.values())


def last_user_index(messages: Sequence[Message]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index]["role"] == USER_ROLE:
            return index
    return None


def user_images(messages: Sequence[Message]) -> tuple[Attachment, ...]:
    """As imagens da última mensagem do usuário: a pergunta."""
    index = last_user_index(messages)
    if index is None:
        return ()
    return unique(tuple(messages[index].get("attachments", ())))


def candidates(messages: Sequence[Message]) -> tuple[Attachment, ...]:
    """As imagens da última mensagem do assistente antes da pergunta — as únicas candidatas (item 7)."""
    end = last_user_index(messages)
    for index in range((len(messages) if end is None else end) - 1, -1, -1):
        if messages[index]["role"] == ASSISTANT_ROLE:
            return unique(tuple(messages[index].get("attachments", ())))
    return ()


def sent_markers(images: Sequence[Attachment]) -> str:
    return " ".join(SENT_MARKER.format(id=image.id) for image in images)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImagePlan:
    """O que a execução faz com as imagens do pedido, decidido antes do primeiro evento.

    `candidates`: as que podem ir à geração (vazio sem `vision` na geração). `viewed`: as que já vão, sem decisão —
    todas as candidatas quando não há quem decida. `gate`: roda a etapa `image_gate` (`chat`/`rag_first` com
    `controller`). `to_controller`: o controller recebe a imagem do usuário (ele declara `vision`).
    """

    candidates: tuple[Attachment, ...] = ()
    viewed: tuple[str, ...] = ()
    gate: bool = False
    user_images: tuple[Attachment, ...] = ()
    to_generation: bool = False
    to_controller: bool = False


def image_plan(
    messages: Sequence[Message],
    *,
    loop_flow: bool,
    controller: bool,
    generation_vision: bool,
    controller_vision: bool,
) -> ImagePlan:
    """A tabela do item 8 do ADR-044.

    `loop_flow`: o `agentic` (o `rag_first` que escala decide no loop, mas o plano dele é o do caminho coberto).
    """
    found = candidates(messages) if generation_vision else ()
    own = user_images(messages)
    plain = ImagePlan(
        user_images=own, to_generation=generation_vision and bool(own), to_controller=controller_vision and bool(own)
    )
    if not found:
        return plain
    if loop_flow:
        return replace(plain, candidates=found)
    if controller:
        return replace(plain, candidates=found, gate=True)
    return replace(plain, candidates=found, viewed=tuple(item.id for item in found))


def chosen(candidates: Sequence[Attachment], viewed: Sequence[str]) -> tuple[Attachment, ...]:
    """As candidatas marcadas para a geração, na ordem em que foram mostradas."""
    wanted = set(viewed)
    return tuple(item for item in candidates if item.id in wanted)


def user_content(
    text: str,
    own: Sequence[Attachment],
    *,
    send_own: bool = False,
    shown: Sequence[Attachment] = (),
) -> str | list[ContentPart]:
    """O conteúdo da última mensagem do usuário ao modelo.

    Sem imagem a enviar, texto — com a marca das próprias imagens que o modelo não recebe. Com imagem, partes: o texto,
    as imagens do usuário e cada candidata escolhida precedida da marca que diz de onde ela veio (item 8).
    """
    if not (send_own and own) and not shown:
        return f"{text}\n{sent_markers(own)}".strip() if own else text
    parts: list[ContentPart] = []
    head = text if send_own or not own else f"{text}\n{sent_markers(own)}".strip()
    if head:
        parts.append({"type": "text", "text": head})
    if send_own:
        parts.extend(image_part(item.mime, item.data) for item in own)
    for item in shown:
        parts.append({"type": "text", "text": SHOWN_MARKER.format(id=item.id)})
        parts.append(image_part(item.mime, item.data))
    return parts


# --- etapa `image_gate` -----------------------------------------------------------------------------------------


def gate_instruction(ids: Sequence[str]) -> str:
    return GATE_INSTRUCTION.format(ids=", ".join(ids))


def gate_format(ids: Sequence[str]) -> dict[str, Any]:
    """`{"view": [<id>…]}`, com cada id restrito às candidatas."""
    schema = {
        "type": "object",
        "properties": {"view": {"type": "array", "items": {"type": "string", "enum": list(ids)}}},
        "required": ["view"],
        "additionalProperties": False,
    }
    return {"type": "json_schema", "json_schema": {"name": GATE_SCHEMA_NAME, "schema": schema}}


def parse_gate(content: str | None, ids: Sequence[str]) -> tuple[str, ...] | None:
    """Os ids escolhidos, na ordem das candidatas; `None` se a saída não é a forma pedida ou cita id estranho."""
    try:
        data = json.loads(content or "")
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, Mapping) or not isinstance(data.get("view"), list):
        return None
    view = data["view"]
    if not all(isinstance(item, str) and item in ids for item in view):
        return None
    return tuple(item for item in ids if item in view)


def candidates_text(ids: Sequence[str]) -> str:
    return CANDIDATES_TEXT.format(ids=", ".join(ids))
