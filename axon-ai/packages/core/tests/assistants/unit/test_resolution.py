"""T032 — gramática do id de modelo e restrição do modelo de geração (research R5)."""

from __future__ import annotations

from typing import Any

import pytest
from assistants_testkit import assistant, config

from axon_ai.assistants.api import RequestRejected
from axon_ai.assistants.domain.definitions import AssistantDefinition, read_config
from axon_ai.assistants.domain.resolution import select_models, split_model_id
from axon_ai.llm.api import ModelRef


def _definition(**models: Any) -> AssistantDefinition:
    body = assistant(
        models=models
        or {"generation": "ollama/qwen3:1.7b", "controller": "ollama/qwen3:8b", "allow": ["ollama/*", "openrouter/*"]}
    )
    definition = read_config(config({"geral": body}), origin="teste").assistants["geral"]
    assert definition.problems == ()
    return definition


@pytest.mark.parametrize(
    ("model", "assistant_name", "requested"),
    [
        ("geral", "geral", None),
        ("geral/qwen3:8b", "geral", "qwen3:8b"),
        ("geral/ollama/qwen3:8b", "geral", "ollama/qwen3:8b"),
        ("generic/openrouter/qwen/qwen3-8b", "generic", "openrouter/qwen/qwen3-8b"),
        ("~meu-rag/ollama/x", "~meu-rag", "ollama/x"),
        ("geral/", "geral", ""),
    ],
)
def test_id_de_modelo_divide_no_primeiro_barra(model: str, assistant_name: str, requested: str | None) -> None:
    selection = split_model_id(model)
    assert (selection.assistant, selection.requested) == (assistant_name, requested)


def test_sem_restricao_usa_os_papeis_declarados() -> None:
    policy = select_models(_definition(), None)
    assert policy.roles["generation"] == ModelRef(provider="ollama", model="qwen3:1.7b")
    assert policy.allow == ("ollama/*", "openrouter/*")


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("qwen3:8b", ModelRef(provider="ollama", model="qwen3:8b")),
        ("ollama/qwen3:14b", ModelRef(provider="ollama", model="qwen3:14b")),
        ("openrouter/qwen/qwen3-8b", ModelRef(provider="openrouter", model="qwen/qwen3-8b")),
    ],
)
def test_modelo_pedido_troca_so_o_papel_generation(requested: str, expected: ModelRef) -> None:
    policy = select_models(_definition(), requested)
    assert policy.roles["generation"] == expected
    assert policy.roles["controller"] == ModelRef(provider="ollama", model="qwen3:8b")
    assert policy.allow == ("ollama/*", "openrouter/*")


@pytest.mark.parametrize("requested", ["", "ollama/", "/qwen3", "openai/gpt-x", "qwen/qwen3-8b"])
def test_pedido_vazio_malformado_ou_fora_da_allowlist_e_recusado(requested: str) -> None:
    with pytest.raises(RequestRejected) as caught:
        select_models(_definition(), requested)
    assert caught.value.field == "model"


def test_mensagem_de_modelo_nao_permitido_nomeia_referencia_e_allowlist() -> None:
    with pytest.raises(RequestRejected, match=r"modelo não permitido: openai/gpt-x; allowlist: ollama/\*"):
        select_models(_definition(generation="ollama/a", allow=["ollama/*"]), "openai/gpt-x")
