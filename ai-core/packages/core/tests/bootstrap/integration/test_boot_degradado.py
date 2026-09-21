"""T015 — falha injetada não derruba o boot (SC-004).

Um pack em erro degrada a etapa e o resto da plataforma atende. É o princípio VII em funcionamento: falha explícita,
sem silêncio e sem tudo-ou-nada.
"""

from __future__ import annotations

from pathlib import Path

from bootstrap_testkit import (
    ASSISTANTS_YAML_SEM_PACK,
    PACKS_YAML_COM_QUEBRADO,
    MemoryConfig,
    body,
    write_config,
)
from fastapi.testclient import TestClient

from ai_core.bootstrap.settings import ConfigurationError, Settings
from ai_core.bootstrap.wiring import platform
from ai_core.packs.api import PackStatus


def test_boot_conclui_com_pack_em_erro_e_a_etapa_fica_degradada(tmp_path: Path) -> None:
    settings = write_config(tmp_path, packs=PACKS_YAML_COM_QUEBRADO, assistants=ASSISTANTS_YAML_SEM_PACK)
    plataforma = platform(config=MemoryConfig(settings))

    assert plataforma.ok, "pack em erro não pode impedir o boot"
    assert plataforma.report.degraded == ("packs",)
    detalhe = next(o.detail for o in plataforma.report.stages if o.name == "packs")
    assert detalhe is not None
    assert "inexistente" in detalhe, "o relatório nomeia o pack que falhou"


def test_o_assistant_que_nao_depende_do_pack_quebrado_atende(tmp_path: Path) -> None:
    settings = write_config(tmp_path, packs=PACKS_YAML_COM_QUEBRADO, assistants=ASSISTANTS_YAML_SEM_PACK)
    plataforma = platform(config=MemoryConfig(settings))

    with TestClient(plataforma.app) as client:
        assert client.post("/v1/chat/completions", json=body()).status_code == 200
        assert client.post("/v1/chat/completions", json=body(model="orfao")).status_code == 404


def test_o_pack_quebrado_aparece_em_erro_no_registro(tmp_path: Path) -> None:
    settings = write_config(tmp_path, packs=PACKS_YAML_COM_QUEBRADO, assistants=ASSISTANTS_YAML_SEM_PACK)
    plataforma = platform(config=MemoryConfig(settings))

    assert plataforma.packs is not None
    entrada = plataforma.packs.entry("inexistente")
    assert entrada is not None
    assert entrada.status is PackStatus.ERROR
    assert entrada.error


def test_configuracao_invalida_impede_o_boot(tmp_path: Path) -> None:
    """SC-002: falha de configuração é detectada antes de a API existir."""
    quebrado = tmp_path / "assistants.yaml"
    quebrado.write_text("assistants:\n  x:\n    models: {}\n", encoding="utf-8")
    settings = Settings(profile="test", assistants_file=quebrado)

    plataforma = platform(config=MemoryConfig(settings))

    assert not plataforma.ok
    falha = plataforma.report.failure()
    assert falha is not None and falha.name == "configuration"
    assert plataforma.app is None, "a API não chega a ser montada"


def test_flow_inexistente_no_assistant_impede_o_boot(tmp_path: Path) -> None:
    arquivo = tmp_path / "assistants.yaml"
    arquivo.write_text(
        "assistants:\n  x:\n    flow: agentic\n    models:\n      generation: ollama/m\n", encoding="utf-8"
    )
    plataforma = platform(config=MemoryConfig(Settings(profile="test", assistants_file=arquivo)))

    assert not plataforma.ok
    falha = plataforma.report.failure()
    assert falha is not None and falha.name == "engine"
    assert "agentic" in (falha.detail or "")


def test_perfil_desconhecido_impede_o_boot() -> None:
    class BadProfile:
        def load(self) -> Settings:
            object.__setattr__(settings := Settings(profile="test"), "profile", "producao")
            return settings

    plataforma = platform(config=BadProfile())

    assert not plataforma.ok
    falha = plataforma.report.failure()
    assert falha is not None and falha.name == "adapters"
    assert isinstance(ConfigurationError("x"), ValueError)
