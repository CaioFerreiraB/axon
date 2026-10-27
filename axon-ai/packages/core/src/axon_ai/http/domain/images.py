"""Imagens na borda da API (ADR-044, itens 5, 6, 7 e 9; research R60): puro, sem I/O e sem framework.

- **A última mensagem do usuário** é validada antes de qualquer custo: só data URI (buscar uma URL seria SSRF), só os
  tipos da lista dos contratos, no teto por imagem e na quantidade máxima. As imagens dela vão ao motor.
- **As mensagens anteriores** nunca travam a conversa: imagem de usuário vira `[imagem <id> enviada pelo usuário]`, de
  assistente vira `[imagem <id> mostrada ao usuário]` — sem `alt`, que veio de fora —, e os bytes são descartados na
  leitura. Só a última mensagem do assistente guarda os bytes, os candidatos do turno (005).
- **A resposta** leva as imagens das tools em markdown com data URI, depois do texto, cada uma em parágrafo próprio.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from axon_ai.http.domain.errors import InvalidRequest
from axon_ai_contracts import ATTACHMENT_MIME_TYPES, Attachment, Message

USER: Final = "user"
ASSISTANT: Final = "assistant"

DEFAULT_MAX_REQUEST_BYTES: Final = 33_554_432
DEFAULT_MAX_INPUT_IMAGE_BYTES: Final = 5_242_880
DEFAULT_MAX_INPUT_IMAGES: Final = 4

SENT: Final = "[imagem {id} enviada pelo usuário]"
SHOWN: Final = "[imagem {id} mostrada ao usuário]"
SENT_UNREADABLE: Final = "[imagem enviada pelo usuário]"
SHOWN_UNREADABLE: Final = "[imagem mostrada ao usuário]"

_DATA_URI: Final = re.compile(r"data:([^;,\s]+);base64,([A-Za-z0-9+/=\s]*)\Z", re.IGNORECASE)
_MARKDOWN_IMAGE: Final = re.compile(r"!\[[^\]\n]*\]\((data:[^)\s]*)\)")
"""O markdown que esta API escreve (item 9) e que o cliente devolve no histórico."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageLimits:
    """Os tetos do operador (011): corpo da requisição, bytes por imagem e imagens na última mensagem do usuário."""

    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    max_input_image_bytes: int = DEFAULT_MAX_INPUT_IMAGE_BYTES
    max_input_images: int = DEFAULT_MAX_INPUT_IMAGES


class VisionUnsupported(InvalidRequest):
    """Imagem na pergunta a um Assistant cujo papel `generation` não enxerga imagem (item 5): 400, nomeando o
    Assistant, antes de qualquer chamada de modelo."""

    def __init__(self, assistant: str) -> None:
        super().__init__(
            f"o Assistant '{assistant}' não aceita imagem: o modelo dele não enxerga imagens; escolha um Assistant "
            "com visão ou mande só texto",
            field="messages",
            code="vision_unsupported",
        )


def decode(url: str) -> tuple[str, bytes] | None:
    """`(mime, bytes)` de um data URI em base64, ou `None` se não é um."""
    match = _DATA_URI.match(url.strip())
    if match is None:
        return None
    try:
        data = base64.b64decode(re.sub(r"\s", "", match.group(2)), validate=True)
    except (binascii.Error, ValueError):
        return None
    return match.group(1).lower(), data


def attachment_of(url: str) -> Attachment | None:
    """O anexo de um data URI aceito; `None` se não decodifica, é de tipo fora da lista ou vazio."""
    decoded = decode(url)
    if decoded is None or decoded[0] not in ATTACHMENT_MIME_TYPES or not decoded[1]:
        return None
    return Attachment(mime=decoded[0], data=decoded[1])


def data_uri(attachment: Attachment) -> str:
    return f"data:{attachment.mime};base64,{base64.b64encode(attachment.data).decode('ascii')}"


# --- leitura das mensagens -----------------------------------------------------------------------------------------


def read_messages(raw: Sequence[Mapping[str, Any]], limits: ImageLimits) -> tuple[Message, ...]:
    """As mensagens do pedido para o motor. Estrutura (`role`) já conferida por quem chama."""
    last_user = max((index for index, item in enumerate(raw) if item.get("role") == USER), default=None)
    last_assistant = max(
        (
            index
            for index, item in enumerate(raw)
            if item.get("role") == ASSISTANT and (last_user is None or index < last_user)
        ),
        default=None,
    )
    messages: list[Message] = []
    for index, item in enumerate(raw):
        role = str(item["role"])
        if index == last_user:
            messages.append(_question(index, item.get("content"), limits))
        elif role == ASSISTANT:
            messages.append(_assistant(index, item.get("content"), keep=index == last_assistant))
        else:
            messages.append(_history(index, role, item.get("content")))
    return tuple(messages)


def _texts_and_images(index: int, content: Any, *, strict: bool) -> list[tuple[str, Any]]:
    """As partes de um `content` em ordem: `("text", texto)` ou `("image", url)`. Fora da última mensagem do usuário,
    parte de outro tipo é ignorada; nela, recusada."""
    if isinstance(content, str):
        return [("text", content)]
    if content is None:
        return []
    if not isinstance(content, Sequence):
        raise InvalidRequest(f"mensagem {index} precisa de 'content' em texto ou em partes", field="messages")
    parts: list[tuple[str, Any]] = []
    for position, part in enumerate(content):
        kind = part.get("type") if isinstance(part, Mapping) else None
        if kind == "text" and isinstance(part.get("text"), str):
            parts.append(("text", part["text"]))
        elif kind == "image_url":
            image = part.get("image_url")
            parts.append(("image", image.get("url") if isinstance(image, Mapping) else image))
        elif strict:
            raise InvalidRequest(
                f"mensagem {index}, parte {position}: só 'text' e 'image_url' são aceitas",
                field=f"messages[{index}].content[{position}]",
            )
    return parts


def _question(index: int, content: Any, limits: ImageLimits) -> Message:
    """A última mensagem do usuário: a pergunta, validada antes de qualquer custo (item 5)."""
    texts: list[str] = []
    images: list[Attachment] = []
    for position, (kind, value) in enumerate(_texts_and_images(index, content, strict=True)):
        if kind == "text":
            texts.append(value)
            continue
        field = f"messages[{index}].content[{position}].image_url"
        images.append(_validated(value, field, limits))
    if len(images) > limits.max_input_images:
        raise InvalidRequest(
            f"a mensagem traz {len(images)} imagens; o máximo é {limits.max_input_images}",
            field=f"messages[{index}].content",
            code="too_many_images",
        )
    text = "\n".join(texts)
    if not text.strip() and not images:
        raise InvalidRequest("a última mensagem de papel 'user' precisa de texto ou imagem", field="messages")
    if not images:
        return {"role": USER, "content": text}
    return {"role": USER, "content": text, "attachments": tuple(images)}


def _validated(url: Any, field: str, limits: ImageLimits) -> Attachment:
    if not isinstance(url, str) or not url.strip().lower().startswith("data:"):
        raise InvalidRequest(
            "imagem só em data URI (data:<tipo>;base64,…): a plataforma não busca endereços",
            field=f"{field}.url",
            code="image_url_not_allowed",
        )
    decoded = decode(url)
    if decoded is None:
        raise InvalidRequest(
            "data URI de imagem inválido: precisa ser base64", field=f"{field}.url", code="invalid_image"
        )
    mime, data = decoded
    if mime not in ATTACHMENT_MIME_TYPES:
        accepted = ", ".join(sorted(ATTACHMENT_MIME_TYPES))
        raise InvalidRequest(
            f"tipo de imagem {mime} não aceito; aceitos: {accepted}",
            field=f"{field}.url",
            code="unsupported_image_type",
        )
    if not data:
        raise InvalidRequest("imagem vazia", field=f"{field}.url", code="invalid_image")
    if len(data) > limits.max_input_image_bytes:
        raise InvalidRequest(
            f"imagem de {len(data)} bytes passa do limite de {limits.max_input_image_bytes}",
            field=f"{field}.url",
            code="image_too_large",
        )
    return Attachment(mime=mime, data=data)


def _history(index: int, role: str, content: Any) -> Message:
    """Mensagem anterior que não é do assistente: as imagens viram marca e os bytes saem (item 5)."""
    pieces: list[str] = []
    for kind, value in _texts_and_images(index, content, strict=False):
        if kind == "text":
            pieces.append(value)
        else:
            image = attachment_of(value) if isinstance(value, str) else None
            pieces.append(SENT.format(id=image.id) if image is not None else SENT_UNREADABLE)
    return {"role": role, "content": "\n".join(pieces)}


def _assistant(index: int, content: Any, *, keep: bool) -> Message:
    """Mensagem do assistente: o markdown com data URI e as partes `image_url` viram a marca; os bytes ficam só na
    última, e só dos tipos aceitos (item 7)."""
    images: list[Attachment] = []

    def shown(url: str) -> str:
        image = attachment_of(url)
        if image is None:
            return SHOWN_UNREADABLE
        if keep:
            images.append(image)
        return SHOWN.format(id=image.id)

    pieces: list[str] = []
    for kind, value in _texts_and_images(index, content, strict=False):
        if kind == "text":
            pieces.append(_MARKDOWN_IMAGE.sub(lambda match: shown(match.group(1)), value))
        else:
            pieces.append(shown(value) if isinstance(value, str) else SHOWN_UNREADABLE)
    message: Message = {"role": ASSISTANT, "content": "\n".join(pieces)}
    unique = tuple({image.id: image for image in images}.values())
    if unique:
        message = {"role": ASSISTANT, "content": message["content"], "attachments": unique}
    return message


# --- conteúdo gravado e resposta ------------------------------------------------------------------------------------


def with_markers(text: str, images: Sequence[Attachment], template: str) -> str:
    """O texto com uma marca por imagem — o que a conversa no Axon guarda no lugar do data URI (item 9)."""
    markers = "\n".join(template.format(id=image.id) for image in images)
    if not markers:
        return text
    return f"{text}\n\n{markers}" if text else markers


def images_markdown(images: Sequence[Attachment]) -> str:
    """As imagens das tools em markdown com data URI, cada uma em parágrafo próprio, para vir depois do texto."""
    return "".join(f"\n\n![{image.alt or 'imagem'}]({data_uri(image)})" for image in images)


def summary(images: Sequence[Attachment]) -> list[dict[str, Any]]:
    """O que `x_axon.attachments` traz de cada imagem: id, tipo e tamanho (item 9)."""
    return [{"id": image.id, "mime": image.mime, "size_bytes": len(image.data)} for image in images]
