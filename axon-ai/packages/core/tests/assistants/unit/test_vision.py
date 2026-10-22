"""ADR-044, item 10 (research R45): `vision` por papel no YAML, na sobreposição de `models`, no rascunho de usuário e
na `ModelPolicy` do grant; `controller` aceito no `chat`."""

from __future__ import annotations

from typing import Any

import pytest
from assistants_testkit import T0, assistant, config

from axon_ai.assistants.api import ModelsOverride, RequestRejected, UserAssistantDraft
from axon_ai.assistants.domain.definitions import AssistantDefinition, read_config
from axon_ai.assistants.domain.overrides import (
    StoredOverride,
    apply_models,
    payload_of,
    read_payload,
    section_fingerprint,
    status_of_override,
)
from axon_ai.assistants.domain.resolution import select_models
from axon_ai.assistants.domain.validation import role_reasons
from axon_ai.llm.api import ModelRef

COM_VISAO: dict[str, Any] = {
    "generation": {"model": "openrouter/openai/gpt-4.1", "vision": True},
    "controller": "openrouter/openai/gpt-4.1-nano",
    "allow": ["openrouter/*"],
}


def _definition(models: Any = COM_VISAO, **fields: Any) -> AssistantDefinition:
    body = assistant(models=models, overrides=["models"], **fields)
    return read_config(config({"x": body}), origin="t").assistants["x"]


def test_papel_em_objeto_com_vision() -> None:
    definition = _definition()
    assert definition.problems == ()
    assert definition.roles["generation"] == ModelRef.parse("openrouter/openai/gpt-4.1")
    assert definition.vision == {"generation"}


@pytest.mark.parametrize(
    ("valor", "campo"),
    [
        ({"model": "openrouter/a/b", "vision": "sim"}, "models.generation.vision"),
        ({"vision": True}, "models.generation.model"),
        ({"model": "openrouter/a/b", "cor": 1}, "models.generation"),
    ],
)
def test_papel_em_objeto_malformado(valor: Any, campo: str) -> None:
    definition = _definition({"generation": valor, "allow": ["openrouter/*"]})
    assert any(problem.startswith(f"{campo}:") for problem in definition.problems), definition.problems


def test_politica_do_grant_leva_vision() -> None:
    assert select_models(_definition(), None).vision == {"generation"}


def test_modelo_pedido_diferente_nao_herda_vision() -> None:
    assert select_models(_definition(), "openrouter/outro/modelo").vision == frozenset()
    assert select_models(_definition(), "openrouter/openai/gpt-4.1").vision == {"generation"}


def test_impressao_digital_sem_vision_nao_muda() -> None:
    """Sobreposições gravadas antes do ADR-044 continuam ativas: sem `vision`, a forma canônica é a de antes."""
    sem = _definition({"generation": "openrouter/a/b", "allow": ["openrouter/*"]})
    com = _definition({"generation": {"model": "openrouter/a/b", "vision": True}, "allow": ["openrouter/*"]})
    import hashlib
    import json

    antiga = json.dumps({"generation": "openrouter/a/b"}, sort_keys=True, separators=(",", ":"))
    assert section_fingerprint(sem, "models") == hashlib.sha256(antiga.encode()).hexdigest()
    assert section_fingerprint(com, "models") != section_fingerprint(sem, "models")


def test_sobreposicao_de_models_com_vision_vai_volta_e_se_aplica() -> None:
    definition = _definition()
    override = ModelsOverride(
        roles={"generation": ModelRef.parse("openrouter/x/y"), "controller": ModelRef.parse("openrouter/x/z")},
        vision=frozenset({"controller"}),
    )
    payload = payload_of(override)
    assert payload["vision"] == ["controller"]
    assert read_payload("models", payload) == override
    assert "vision" not in payload_of(ModelsOverride(roles=override.roles))
    assert apply_models(definition, override).vision == {"controller"}
    stored = StoredOverride(
        assistant="x",
        section="models",
        payload=payload,
        fingerprint=section_fingerprint(definition, "models"),
        version=1,
        updated_by="user:root",
        updated_at=T0,
    )
    assert status_of_override(definition, stored).state == "active"


def test_sobreposicao_com_vision_em_papel_ausente() -> None:
    with pytest.raises(ValueError, match="generation"):
        ModelsOverride(roles={"controller": ModelRef.parse("openrouter/x/z")}, vision=frozenset({"generation"}))
    assert read_payload("models", {"roles": {"generation": "openrouter/a/b"}, "vision": ["controller"]}) is None


def test_rascunho_de_usuario_com_vision() -> None:
    models = {"generation": ModelRef.parse("ollama/m")}
    assert UserAssistantDraft(name="meu", models=models, vision=frozenset({"generation"})).vision == {"generation"}
    with pytest.raises(RequestRejected):
        UserAssistantDraft(name="meu", models=models, vision=frozenset({"controller"}))


def test_controller_declarado_no_chat_nao_e_motivo() -> None:
    definition = _definition(flow="chat")
    assert role_reasons(definition, flow="chat", flow_roles={"chat": ("generation",)}) == ()
