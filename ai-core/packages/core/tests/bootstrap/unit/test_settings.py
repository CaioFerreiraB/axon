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


# --- Fase 2 (T021; contracts/configuration.md, "Fase 2") -------------------------------------------------------------

DSN = "postgresql://ai:segredo-do-banco@db.interno:5432/ai"
DEV_KEY = "aic_0123456789abcdef_segredo-dev"


def test_variaveis_novas_tem_defaults() -> None:
    settings = EnvConfigSource({}).load()
    assert settings.database_url is None and settings.dev_api_key is None
    assert settings.oidc_issuer is None and settings.oidc_audience is None and settings.oidc_jwks_url is None
    assert (settings.oidc_subject_claim, settings.oidc_groups_claim) == ("sub", "groups")
    assert settings.conversation_retention_days == 180
    assert settings.conversation_expiry_interval == 3600.0


def test_variaveis_novas_sao_lidas() -> None:
    settings = EnvConfigSource(
        {
            "AI_CORE_PROFILE": "persistent",
            "AI_CORE_DATABASE_URL": DSN,
            "AI_CORE_OIDC_ISSUER": "https://idp.exemplo.test",
            "AI_CORE_OIDC_AUDIENCE": "ai-core",
            "AI_CORE_OIDC_JWKS_URL": "https://idp.exemplo.test/jwks",
            "AI_CORE_OIDC_SUBJECT_CLAIM": "preferred_username",
            "AI_CORE_OIDC_GROUPS_CLAIM": "roles",
            "AI_CORE_CONVERSATION_RETENTION_DAYS": "30",
            "AI_CORE_CONVERSATION_EXPIRY_INTERVAL": "60",
        }
    ).load()
    assert settings.profile == "persistent" and settings.database_url == DSN
    assert (settings.oidc_issuer, settings.oidc_audience) == ("https://idp.exemplo.test", "ai-core")
    assert settings.oidc_jwks_url == "https://idp.exemplo.test/jwks"
    assert (settings.oidc_subject_claim, settings.oidc_groups_claim) == ("preferred_username", "roles")
    assert (settings.conversation_retention_days, settings.conversation_expiry_interval) == (30, 60.0)


def test_chave_de_desenvolvimento_no_memory() -> None:
    assert EnvConfigSource({"AI_CORE_DEV_API_KEY": DEV_KEY}).load().dev_api_key == DEV_KEY


@pytest.mark.parametrize(
    ("environ", "variable"),
    [
        ({"AI_CORE_PROFILE": "persistent"}, "AI_CORE_DATABASE_URL"),
        ({"AI_CORE_OIDC_ISSUER": "https://idp"}, "AI_CORE_OIDC_AUDIENCE"),
        ({"AI_CORE_DEV_API_KEY": "nao-e-chave"}, "AI_CORE_DEV_API_KEY"),
        ({"AI_CORE_PROFILE": "persistent", "AI_CORE_DATABASE_URL": DSN, "AI_CORE_DEV_API_KEY": DEV_KEY},
         "AI_CORE_DEV_API_KEY"),
        ({"AI_CORE_CONVERSATION_RETENTION_DAYS": "0"}, "AI_CORE_CONVERSATION_RETENTION_DAYS"),
        ({"AI_CORE_CONVERSATION_EXPIRY_INTERVAL": "-5"}, "AI_CORE_CONVERSATION_EXPIRY_INTERVAL"),
    ],
)
def test_recusas_nomeiam_a_variavel(environ: dict[str, str], variable: str) -> None:
    with pytest.raises(ConfigurationError, match=variable):
        EnvConfigSource(environ).load()


@pytest.mark.parametrize(
    "environ",
    [
        {"AI_CORE_DEV_API_KEY": "nao-e-chave-segredo-123"},
        {"AI_CORE_PROFILE": "persistent", "AI_CORE_DATABASE_URL": DSN, "AI_CORE_DEV_API_KEY": DEV_KEY},
    ],
)
def test_mensagem_de_erro_nunca_contem_segredo(environ: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError) as caught:
        EnvConfigSource(environ).load()
    for secret in (DSN, DEV_KEY, "nao-e-chave-segredo-123", "segredo"):
        assert secret not in str(caught.value)


def test_repr_nao_mostra_segredos() -> None:
    settings = Settings(profile="persistent", database_url=DSN)
    memoria = Settings(profile="memory", dev_api_key=DEV_KEY)
    for texto in (repr(settings), str(settings), repr(memoria)):
        assert "segredo" not in texto
