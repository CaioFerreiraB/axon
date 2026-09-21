"""T008 — configuração do operador (contracts/configuration.md), validada antes de qualquer etapa."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_core.bootstrap.settings import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_PORT,
    ConfigurationError,
    EnvConfigSource,
    InMemoryConfigSource,
    Settings,
)


def test_defaults_quando_nada_e_configurado() -> None:
    settings = EnvConfigSource({}).load()
    assert settings.profile == "memory"
    assert settings.ollama_base_url == DEFAULT_OLLAMA_BASE_URL
    assert settings.port == DEFAULT_PORT
    assert settings.packs_file is None
    assert settings.assistants_file is None


def test_variaveis_sao_lidas() -> None:
    settings = EnvConfigSource(
        {
            "AI_CORE_PROFILE": "test",
            "AI_CORE_PACKS_FILE": "/etc/packs.yaml",
            "AI_CORE_ASSISTANTS_FILE": "/etc/assistants.yaml",
            "AI_CORE_TRACE_DIR": "/var/trace",
            "AI_CORE_HOST": "0.0.0.0",
            "AI_CORE_PORT": "9000",
            "AI_CORE_SHUTDOWN_GRACE_SECONDS": "30",
        }
    ).load()

    assert settings.profile == "test"
    assert settings.packs_file == Path("/etc/packs.yaml")
    assert settings.assistants_file == Path("/etc/assistants.yaml")
    assert settings.trace_dir == Path("/var/trace")
    assert (settings.host, settings.port) == ("0.0.0.0", 9000)
    assert settings.shutdown_grace_seconds == 30.0


def test_perfil_desconhecido_nomeia_a_variavel() -> None:
    with pytest.raises(ConfigurationError, match="AI_CORE_PROFILE"):
        EnvConfigSource({"AI_CORE_PROFILE": "producao"}).load()


@pytest.mark.parametrize("port", ["0", "70000", "-1"])
def test_porta_fora_da_faixa_e_recusada(port: str) -> None:
    with pytest.raises(ConfigurationError, match="AI_CORE_PORT"):
        EnvConfigSource({"AI_CORE_PORT": port}).load()


def test_porta_nao_numerica_e_recusada() -> None:
    with pytest.raises(ConfigurationError, match="AI_CORE_PORT"):
        EnvConfigSource({"AI_CORE_PORT": "oito mil"}).load()


def test_prazo_negativo_e_recusado() -> None:
    with pytest.raises(ConfigurationError, match="SHUTDOWN_GRACE_SECONDS"):
        EnvConfigSource({"AI_CORE_SHUTDOWN_GRACE_SECONDS": "-1"}).load()


def test_endereco_do_provider_vazio_e_recusado() -> None:
    with pytest.raises(ConfigurationError, match="OLLAMA_BASE_URL"):
        EnvConfigSource({"AI_CORE_OLLAMA_BASE_URL": "  "}).load()


def test_configuracao_em_memoria_devolve_o_que_recebeu() -> None:
    settings = Settings(profile="test", host="localhost")
    assert InMemoryConfigSource(settings).load() is settings


def test_settings_e_imutavel() -> None:
    settings = Settings()
    with pytest.raises(AttributeError):
        settings.port = 1  # type: ignore[misc]
