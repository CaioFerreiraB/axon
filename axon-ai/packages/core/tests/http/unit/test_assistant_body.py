"""T032 — JSON ⇄ rascunho de Assistant de usuário (research R19): o mapeamento é puro, as regras são da 003."""

from __future__ import annotations

from typing import Any

import pytest

from axon_ai.assistants.api import DraftLimits, RequestRejected
from axon_ai.http.domain.assistant_body import draft_from_json, draft_json
from axon_ai.http.domain.errors import InvalidRequest
from axon_ai.llm.api import ModelRef

COMPLETO = {
    "name": "meu-rag",
    "description": "meu assistente",
    "flow": "chat",
    "packs": ["generic"],
    "mcp": ["agenda"],
    "collections": [],
    "models": {"generation": "ollama/qwen3:1.7b", "controller": "openrouter/qwen/qwen3-8b"},
    "limits": {"rpm": 5},
    "allowed_tools": ["calculate"],
    "write_tools": [],
}


def test_ida_e_volta() -> None:
    draft = draft_from_json(COMPLETO)
    assert draft.models["controller"] == ModelRef(provider="openrouter", model="qwen/qwen3-8b")
    assert draft.limits == DraftLimits(rpm=5)
    assert draft_json(draft) == COMPLETO | {"limits": {"rpm": 5, "max_iterations": None, "max_context_tokens": None}}


def test_nome_do_caminho_preenche_o_corpo() -> None:
    body = {k: v for k, v in COMPLETO.items() if k != "name"}
    assert draft_from_json(body, name="~meu-rag").name == "meu-rag"


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"extra": 1}, "extra"),
        ({"packs": "generic"}, "packs"),
        ({"models": {"generation": "sem-barra"}}, "models.generation"),
        ({"models": ["ollama/x"]}, "models"),
        ({"limits": {"rpm": "5"}}, "limits.rpm"),
        ({"limits": {"tokens": 5}}, "limits.tokens"),
        ({"visibility": "public"}, "visibility"),
        ({"auth": {"allow": ["*"]}}, "auth"),
    ],
)
def test_corpo_invalido_nomeia_o_campo(overrides: dict[str, Any], field: str) -> None:
    with pytest.raises((InvalidRequest, RequestRejected)) as caught:
        draft_from_json(COMPLETO | overrides)
    assert caught.value.field == field


def test_sem_models_generation_e_recusado() -> None:
    with pytest.raises(RequestRejected) as caught:
        draft_from_json(COMPLETO | {"models": {"controller": "ollama/x"}})
    assert caught.value.field == "models.generation"
