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
        (
            {"AI_CORE_PROFILE": "persistent", "AI_CORE_DATABASE_URL": DSN, "AI_CORE_DEV_API_KEY": DEV_KEY},
            "AI_CORE_DEV_API_KEY",
        ),
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


# --- Fase 3 (T035; research R27): registry MCP e gateway de tools ---------------------------------------------------


@pytest.mark.us2
def test_variaveis_da_fase_3_tem_defaults() -> None:
    settings = EnvConfigSource({}).load()
    assert settings.mcp_file is None
    assert settings.mcp_discovery_ttl == 300.0
    assert settings.tool_timeout_ms == 30_000
    assert settings.tool_max_response_bytes == 16_384


@pytest.mark.us2
def test_variaveis_da_fase_3_sao_lidas(tmp_path: Path) -> None:
    settings = EnvConfigSource(
        {
            "AI_CORE_MCP_FILE": str(tmp_path / "mcp.yaml"),
            "AI_CORE_MCP_DISCOVERY_TTL": "60",
            "AI_CORE_TOOL_TIMEOUT_MS": "5000",
            "AI_CORE_TOOL_MAX_RESPONSE_BYTES": "4096",
        }
    ).load()
    assert settings.mcp_file == tmp_path / "mcp.yaml"
    assert settings.mcp_discovery_ttl == 60.0
    assert settings.tool_timeout_ms == 5000
    assert settings.tool_max_response_bytes == 4096


@pytest.mark.us2
@pytest.mark.parametrize(
    ("environ", "variable"),
    [
        ({"AI_CORE_MCP_DISCOVERY_TTL": "0"}, "AI_CORE_MCP_DISCOVERY_TTL"),
        ({"AI_CORE_MCP_DISCOVERY_TTL": "-1"}, "AI_CORE_MCP_DISCOVERY_TTL"),
        ({"AI_CORE_TOOL_TIMEOUT_MS": "999"}, "AI_CORE_TOOL_TIMEOUT_MS"),
        ({"AI_CORE_TOOL_TIMEOUT_MS": "300001"}, "AI_CORE_TOOL_TIMEOUT_MS"),
        ({"AI_CORE_TOOL_MAX_RESPONSE_BYTES": "1023"}, "AI_CORE_TOOL_MAX_RESPONSE_BYTES"),
        ({"AI_CORE_TOOL_MAX_RESPONSE_BYTES": "1048577"}, "AI_CORE_TOOL_MAX_RESPONSE_BYTES"),
        ({"AI_CORE_TOOL_TIMEOUT_MS": "rapido"}, "AI_CORE_TOOL_TIMEOUT_MS"),
    ],
)
def test_recusas_da_fase_3_nomeiam_a_variavel(environ: dict[str, str], variable: str) -> None:
    with pytest.raises(ConfigurationError, match=variable):
        EnvConfigSource(environ).load()


@pytest.mark.us2
def test_credencial_de_mcp_nao_passa_pela_configuracao() -> None:
    """`AI_CORE_MCP_SECRET_*` é lida pela 007 só ao montar a operação — nunca por `Settings` (FR-009, R27)."""
    settings = EnvConfigSource({"AI_CORE_MCP_SECRET_X": "segredo-x"}).load()
    assert "segredo-x" not in repr(settings)
    assert "segredo-x" not in str(settings)


# --- Fase 5 (005 T086; research R44 da 005): os números do `rag_first` ------------------------------------------------


@pytest.mark.us3
def test_variaveis_da_fase_5_tem_defaults() -> None:
    settings = EnvConfigSource({}).load()
    assert (settings.rag_candidates, settings.rag_passages, settings.rag_min_score) == (20, 5, None)


@pytest.mark.us3
def test_variaveis_da_fase_5_sao_lidas() -> None:
    settings = EnvConfigSource(
        {"AI_CORE_RAG_CANDIDATES": "30", "AI_CORE_RAG_PASSAGES": "8", "AI_CORE_RAG_MIN_SCORE": "0.86"}
    ).load()
    assert (settings.rag_candidates, settings.rag_passages, settings.rag_min_score) == (30, 8, 0.86)


@pytest.mark.us3
def test_limiar_vazio_e_sem_limiar() -> None:
    assert EnvConfigSource({"AI_CORE_RAG_MIN_SCORE": ""}).load().rag_min_score is None


@pytest.mark.us3
@pytest.mark.parametrize(
    ("environ", "variable"),
    [
        ({"AI_CORE_RAG_CANDIDATES": "0"}, "AI_CORE_RAG_CANDIDATES"),
        ({"AI_CORE_RAG_CANDIDATES": "-3"}, "AI_CORE_RAG_CANDIDATES"),
        ({"AI_CORE_RAG_CANDIDATES": "vinte"}, "AI_CORE_RAG_CANDIDATES"),
        ({"AI_CORE_RAG_PASSAGES": "0"}, "AI_CORE_RAG_PASSAGES"),
        ({"AI_CORE_RAG_MIN_SCORE": "1.5"}, "AI_CORE_RAG_MIN_SCORE"),
        ({"AI_CORE_RAG_MIN_SCORE": "-0.1"}, "AI_CORE_RAG_MIN_SCORE"),
        ({"AI_CORE_RAG_MIN_SCORE": "nan"}, "AI_CORE_RAG_MIN_SCORE"),
        ({"AI_CORE_RAG_MIN_SCORE": "alto"}, "AI_CORE_RAG_MIN_SCORE"),
    ],
)
def test_recusas_da_fase_5_nomeiam_a_variavel(environ: dict[str, str], variable: str) -> None:
    with pytest.raises(ConfigurationError, match=variable):
        EnvConfigSource(environ).load()


# --- Fase 7 (008 T073): admissão da API — limite, fila e espera (008 FR-016, research R36) ----------------------------


def test_variaveis_da_fase_7_tem_defaults() -> None:
    settings = EnvConfigSource({}).load()
    assert (settings.max_executions, settings.queue_size, settings.queue_wait_ms) == (2, 8, 60_000)


def test_variaveis_da_fase_7_sao_lidas() -> None:
    settings = EnvConfigSource(
        {"AI_CORE_MAX_EXECUTIONS": "4", "AI_CORE_QUEUE_SIZE": "0", "AI_CORE_QUEUE_WAIT_MS": "1500"}
    ).load()
    assert (settings.max_executions, settings.queue_size, settings.queue_wait_ms) == (4, 0, 1500)


@pytest.mark.parametrize(
    ("environ", "variable"),
    [
        ({"AI_CORE_MAX_EXECUTIONS": "0"}, "AI_CORE_MAX_EXECUTIONS"),
        ({"AI_CORE_MAX_EXECUTIONS": "65"}, "AI_CORE_MAX_EXECUTIONS"),
        ({"AI_CORE_QUEUE_SIZE": "-1"}, "AI_CORE_QUEUE_SIZE"),
        ({"AI_CORE_QUEUE_SIZE": "1001"}, "AI_CORE_QUEUE_SIZE"),
        ({"AI_CORE_QUEUE_WAIT_MS": "0"}, "AI_CORE_QUEUE_WAIT_MS"),
        ({"AI_CORE_QUEUE_WAIT_MS": "600001"}, "AI_CORE_QUEUE_WAIT_MS"),
        ({"AI_CORE_QUEUE_WAIT_MS": "um minuto"}, "AI_CORE_QUEUE_WAIT_MS"),
    ],
)
def test_recusas_da_fase_7_nomeiam_a_variavel(environ: dict[str, str], variable: str) -> None:
    with pytest.raises(ConfigurationError, match=variable):
        EnvConfigSource(environ).load()
