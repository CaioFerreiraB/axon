"""Imagens nas mensagens ao modelo (ADR-044, itens 10 e 11; research R32). Puro.

A guarda de `vision` é a irmã da de `response_format` (`output.py`): papel sem `vision` que recebe imagem é erro de
programação de quem chama — a 005 nunca a envia —, recusado antes do provider. No `model_exchange`, a imagem vira a
marca com o id do conteúdo, nunca os bytes.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence

from axon_ai.llm.api import ModelMessage, ModelRole, has_image
from axon_ai_contracts import Attachment


def vision_problem(role: ModelRole, messages: Sequence[ModelMessage], *, vision: bool) -> str | None:
    """O motivo da recusa, ou `None`: imagem só vai a papel que declara `vision`."""
    if vision or not any(has_image(message) for message in messages):
        return None
    return f"o papel '{role}' não declara vision: mensagem com imagem recusada antes do provider"


def image_marker(url: str) -> str:
    """A marca de uma imagem no texto do `model_exchange`: o id do conteúdo, como em toda parte (ADR-044, item 1)."""
    header, _, encoded = url.partition(",")
    mime = header.removeprefix("data:").partition(";")[0]
    try:
        return f"[imagem {Attachment(mime=mime, data=base64.b64decode(encoded, validate=True)).id}]"
    except (binascii.Error, TypeError, ValueError):
        return "[imagem]"
