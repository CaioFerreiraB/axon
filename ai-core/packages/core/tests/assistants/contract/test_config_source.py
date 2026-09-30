"""T011 — conformidade da porta `AssistantConfigSource` (contracts/ports.md): YAML e memória interpretam igual."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from assistants_testkit import assistant, config, policy, private

from ai_core.assistants.adapters.assistants_yaml import YamlAssistantConfigSource
from ai_core.assistants.adapters.memory import InMemoryAssistantConfigSource
from ai_core.assistants.api import AssistantsConfigError

DADOS = config(
    {"geral": assistant(), "interno": private(), "quebrado": assistant(visibility=None)},
    policies=[policy(match="group:chefia"), policy()],
)


def test_us1_yaml_e_memoria_produzem_a_mesma_configuracao(tmp_path: Path) -> None:
    arquivo = tmp_path / "assistants.yaml"
    arquivo.write_text(yaml.safe_dump(DADOS, allow_unicode=True), encoding="utf-8")

    do_arquivo = YamlAssistantConfigSource(arquivo).load()
    da_memoria = InMemoryAssistantConfigSource(DADOS).load()

    assert do_arquivo.policies == da_memoria.policies
    assert do_arquivo.admin_group == da_memoria.admin_group
    assert dict(do_arquivo.assistants).keys() == dict(da_memoria.assistants).keys()
    for name in do_arquivo.assistants:
        assert do_arquivo.assistants[name].problems == da_memoria.assistants[name].problems
        assert do_arquivo.assistants[name] == da_memoria.assistants[name]


def test_us1_arquivo_ausente_e_erro_que_nomeia_o_caminho(tmp_path: Path) -> None:
    ausente = tmp_path / "nao-existe.yaml"
    with pytest.raises(AssistantsConfigError, match=r"nao-existe\.yaml"):
        YamlAssistantConfigSource(ausente).load()


def test_us1_yaml_invalido_e_erro_de_arquivo(tmp_path: Path) -> None:
    arquivo = tmp_path / "assistants.yaml"
    arquivo.write_text("assistants: [geral\n", encoding="utf-8")
    with pytest.raises(AssistantsConfigError, match="YAML inválido"):
        YamlAssistantConfigSource(arquivo).load()


def test_us1_erro_de_arquivo_nomeia_o_arquivo(tmp_path: Path) -> None:
    arquivo = tmp_path / "assistants.yaml"
    arquivo.write_text("assistentes: {}\n", encoding="utf-8")
    with pytest.raises(AssistantsConfigError, match=r"assistants\.yaml.*assistentes"):
        YamlAssistantConfigSource(arquivo).load()
