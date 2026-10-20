"""Listagem de modelos (US2, research R16): cada Assistant que o Principal resolve vira um "model" com id curto."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from axon_ai.assistants.api import AssistantSummary
from axon_ai.http.domain.errors import EXTRA


def model_list(summaries: Sequence[AssistantSummary], *, owner: str, created: datetime) -> dict[str, Any]:
    """O formato de `GET /models` da OpenAI. `owner` é quem lista: os Assistants de usuário listados são dele."""
    return {"object": "list", "data": [model_entry(summary, owner=owner, created=created) for summary in summaries]}


def model_entry(summary: AssistantSummary, *, owner: str, created: datetime) -> dict[str, Any]:
    """Id = nome do Assistant, estável quando o operador troca o modelo (clarificação de 2026-09-30)."""
    return {
        "id": summary.name,
        "object": "model",
        "created": int(created.timestamp()),
        "owned_by": "system" if summary.origin == "system" else owner,
        EXTRA: {
            "generation": str(summary.generation),
            "description": summary.description,
            "origin": summary.origin,
            "allow": list(summary.allow),
        },
    }
