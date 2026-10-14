"""T012 e T023 — conformidade dos perfis (contracts/profiles.md, inclusive a seção "Fase 2")."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from psycopg_pool import AsyncConnectionPool

from ai_core.assistants.adapters.api_keys_postgres import PostgresApiKeyStore
from ai_core.assistants.adapters.assistants_postgres import PostgresUserAssistantStore
from ai_core.assistants.adapters.memory import DisabledOidcVerifier, StaticOidcVerifier
from ai_core.assistants.adapters.oidc import JwksOidcVerifier
from ai_core.assistants.adapters.tokens import SecretsTokenGenerator
from ai_core.assistants.api import PRIVATE_SURFACE, PUBLIC_SURFACE
from ai_core.assistants.domain.access import OidcClaims
from ai_core.assistants.domain.definitions import AssistantsConfig
from ai_core.assistants.service import AccessService
from ai_core.bootstrap.profiles import (
    DEFAULT_PUBLIC_AUDIENCE,
    DEV_SUBJECT,
    FIXED_TIME,
    NOT_OVERRIDABLE,
    PROFILES,
    REQUIRED_PORTS,
    STORAGE_PORTS,
    TEST_ADMIN_GROUP,
    TEST_API_KEY,
    TEST_OIDC_TOKEN,
    TEST_SUBJECT,
    Profile,
    lacks_credentials,
    profile_for,
    validate,
)
from ai_core.bootstrap.settings import ConfigurationError, Settings
from ai_core.capabilities.adapters.audit_postgres import PostgresAuditLog
from ai_core.capabilities.adapters.memory import InMemoryAuditLog
from ai_core.http.adapters.conversations_postgres import PostgresConversationStore
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.adapters.ollama import OllamaProvider
from ai_core.llm.adapters.openai import OpenAIProvider
from ai_core.llm.adapters.openrouter import OpenRouterProvider
from ai_core.llm.adapters.secrets import EnvSecretResolver as LlmEnvSecretResolver
from ai_core.llm.adapters.secrets import InMemorySecretResolver as LlmInMemorySecretResolver
from ai_core.mcp.adapters.dns_system import SystemDnsResolver
from ai_core.mcp.adapters.memory import (
    FixedDnsResolver,
    InMemoryDiscoveryCache,
    InMemorySecretResolver,
    InMemoryServerStore,
    ScriptedMcpTransport,
)
from ai_core.mcp.adapters.registry_postgres import PostgresServerStore
from ai_core.mcp.adapters.secrets_env import EnvSecretResolver
from ai_core.mcp.adapters.transport_http import HttpMcpTransport
from ai_core.mcp.adapters.transport_stdio import StdioMcpTransport
from ai_core.mcp.ports import McpConfig
from ai_core.observability.adapters.jsonl import JsonlTraceBackend
from ai_core.observability.adapters.memory import InMemoryTraceBackend


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_os_perfis_atendem_todas_as_portas_exigidas(name: str) -> None:
    profile = profile_for(name)
    assert set(REQUIRED_PORTS) <= set(profile.factories)


def test_perfil_incompleto_e_recusado_nomeando_a_porta() -> None:
    incompleto = Profile(name="furado", factories={"clock": lambda _s, _p: object()})
    with pytest.raises(ConfigurationError) as error:
        validate(incompleto)
    assert "trace" in str(error.value)
    assert "providers" in str(error.value)


def test_perfil_desconhecido_e_recusado() -> None:
    with pytest.raises(ConfigurationError, match="producao"):
        profile_for("producao")


def test_no_perfil_de_teste_o_provider_e_simulado_e_o_trace_e_de_memoria() -> None:
    profile = profile_for("test")
    settings = Settings(profile="test")
    assert isinstance(profile.build("providers", settings)["ollama"], ScriptedProvider)
    assert isinstance(profile.build("trace", settings), InMemoryTraceBackend)


def test_no_perfil_de_memoria_o_provider_e_o_ollama() -> None:
    profile = profile_for("memory")
    providers = profile.build(
        "providers", Settings(ollama_base_url="http://local/v1"), {"llm_secrets": LlmInMemorySecretResolver()}
    )
    assert isinstance(providers["ollama"], OllamaProvider)


def test_trace_de_memoria_sem_diretorio_e_jsonl_com_diretorio(tmp_path: Path) -> None:
    profile = profile_for("memory")
    assert isinstance(profile.build("trace", Settings()), InMemoryTraceBackend)
    assert isinstance(profile.build("trace", Settings(trace_dir=tmp_path)), JsonlTraceBackend)


def test_o_relogio_do_perfil_de_teste_e_fixo() -> None:
    clock = profile_for("test").build("clock", Settings(profile="test"))
    assert clock.now() == clock.now()
    assert clock.now().tzinfo is not None


# --- Fase 2 (T023; contracts/profiles.md, "Fase 2") -------------------------------------------------------------------

DSN = "postgresql://ai:segredo@127.0.0.1:1/ai"
"""Porta 1: nada escuta ali. Construir o perfil persistente não pode conectar — se conectasse, este teste pendura ou
falha."""

DEV_KEY = "aic_0123456789abcdef_segredo-dev"


def _access(parts: dict[str, Any], *, admin_group: str | None = None) -> AccessService:
    return AccessService(
        keys=parts["api_keys"],
        oidc=parts["oidc"],
        tokens=SecretsTokenGenerator(),
        clock=parts["clock"],
        claims=OidcClaims(),
        admin_group=admin_group,
    )


def _config(admin_group: str | None) -> AssistantsConfig:
    return AssistantsConfig(admin_group=admin_group)


def test_nenhum_perfil_tem_autenticador_anonimo() -> None:
    """FR-015: a porta do autenticador anônimo saiu da lista; a autenticação é a da 003 em todos os perfis."""
    assert "authenticator" not in REQUIRED_PORTS
    for name in PROFILES:
        assert "authenticator" not in profile_for(name).factories


def test_a_ordem_da_lista_e_a_ordem_de_construcao() -> None:
    """R12: o armazenamento vem depois de `database`, e as fábricas veem o que já foi construído."""
    assert REQUIRED_PORTS.index("database") < REQUIRED_PORTS.index("api_keys")
    assert REQUIRED_PORTS.index("clock") < REQUIRED_PORTS.index("api_keys")
    built = profile_for("test").build_all(Settings(profile="test"))
    assert tuple(built) == REQUIRED_PORTS


def test_o_persistent_constroi_o_pool_fechado_e_os_adapters_postgres_sem_conectar() -> None:
    settings = Settings(profile="persistent", database_url=DSN)
    built = profile_for("persistent").build_all(settings, {"assistants_config": _config(None)})

    assert isinstance(built["database"], AsyncConnectionPool)
    assert built["database"].closed, "o pool abre no ciclo de vida da app, no laço do servidor (R13)"
    assert isinstance(built["api_keys"], PostgresApiKeyStore)
    assert isinstance(built["user_assistants"], PostgresUserAssistantStore)
    assert isinstance(built["conversations"], PostgresConversationStore)
    assert isinstance(built["oidc"], DisabledOidcVerifier), "sem emissor, a superfície pública recusa tudo"


def test_o_pool_do_persistent_nao_expoe_a_url() -> None:
    built = profile_for("persistent").build("database", Settings(profile="persistent", database_url=DSN), {})
    assert "segredo" not in repr(built) and "segredo" not in str(built)


def test_o_perfil_de_teste_nao_instancia_nada_que_fale_com_rede() -> None:
    built = profile_for("test").build_all(Settings(profile="test"))

    assert built["database"] is None
    assert isinstance(built["providers"]["ollama"], ScriptedProvider)
    assert isinstance(built["oidc"], StaticOidcVerifier)
    for port in ("api_keys", "user_assistants", "conversations"):
        assert type(built[port]).__module__.endswith("memory"), f"{port}: {type(built[port])}"


async def test_as_credenciais_exportadas_autenticam_pelos_adapters_do_perfil_de_teste() -> None:
    built = profile_for("test").build_all(Settings(profile="test"))
    access = _access(built, admin_group=TEST_ADMIN_GROUP)

    publico = await access.authenticate(surface=PUBLIC_SURFACE, credential=TEST_OIDC_TOKEN)
    privado = await access.authenticate(surface=PRIVATE_SURFACE, credential=TEST_API_KEY)

    assert publico is not None and publico.subject == TEST_SUBJECT and publico.scheme == "oidc"
    assert privado is not None and privado.subject == TEST_SUBJECT and privado.scheme == "api_key"
    assert TEST_ADMIN_GROUP in privado.groups and access.is_admin(privado)
    assert await access.authenticate(surface=PUBLIC_SURFACE, credential=None) is None
    assert await access.authenticate(surface=PUBLIC_SURFACE, credential=TEST_API_KEY) is None
    assert await access.authenticate(surface=PRIVATE_SURFACE, credential=TEST_OIDC_TOKEN) is None


async def test_o_token_de_teste_vale_no_instante_do_relogio_fixo() -> None:
    built = profile_for("test").build_all(Settings(profile="test"))
    claims = await built["oidc"].verify(TEST_OIDC_TOKEN, audience=DEFAULT_PUBLIC_AUDIENCE)
    assert claims is not None
    assert claims["exp"] > FIXED_TIME.timestamp() >= claims["iat"]


async def test_o_memory_semeia_a_chave_de_desenvolvimento_no_grupo_de_administracao() -> None:
    settings = Settings(profile="memory", dev_api_key=DEV_KEY)
    built = profile_for("memory").build_all(settings, {"assistants_config": _config("operadores")})
    access = _access(built, admin_group="operadores")

    principal = await access.authenticate(surface=PRIVATE_SURFACE, credential=DEV_KEY)

    assert principal is not None and principal.subject == DEV_SUBJECT
    assert access.is_admin(principal)


async def test_o_memory_sem_chave_nem_oidc_recusa_toda_credencial() -> None:
    built = profile_for("memory").build_all(Settings(profile="memory"), {"assistants_config": _config(None)})
    access = _access(built)

    assert isinstance(built["oidc"], DisabledOidcVerifier)
    assert await access.authenticate(surface=PRIVATE_SURFACE, credential=DEV_KEY) is None
    assert await access.authenticate(surface=PUBLIC_SURFACE, credential="qualquer") is None
    assert lacks_credentials(Settings(profile="memory"))
    assert not lacks_credentials(Settings(profile="memory", dev_api_key=DEV_KEY))
    assert not lacks_credentials(Settings(profile="memory", oidc_issuer="https://idp", oidc_audience="ai"))
    assert not lacks_credentials(Settings(profile="test"))


def test_com_emissor_configurado_o_oidc_e_o_verificador_jwks() -> None:
    settings = Settings(profile="memory", oidc_issuer="https://idp.exemplo.test", oidc_audience="ai-core")
    built = profile_for("memory").build_all(settings, {"assistants_config": _config(None)})
    assert isinstance(built["oidc"], JwksOidcVerifier)


def test_ids_de_conversa_tem_fabrica_propria() -> None:
    """R19: no perfil de teste, `t-1` — e não o `req-1` dos ids de requisição."""
    teste = profile_for("test").build_all(Settings(profile="test"))
    assert teste["conversation_ids"] is not teste["request_ids"]
    assert teste["conversation_ids"].next() == "t-1"
    assert teste["request_ids"].next() == "req-1"

    memoria = profile_for("memory").build_all(Settings(), {"assistants_config": _config(None)})
    assert memoria["conversation_ids"] is not memoria["request_ids"]
    assert memoria["conversation_ids"].next() != memoria["conversation_ids"].next()


# --- Fase 3 (T037; research R22): portas da 007 e da 004 -----------------------------------------------------------

NEW_PORTS = ("mcp_store", "mcp_dns", "mcp_transports", "mcp_secrets", "mcp_cache", "audit")


@pytest.mark.us2
def test_as_portas_da_fase_3_fecham_a_lista_e_as_de_armazenamento_sao_reconstruidas() -> None:
    # as da Fase 3 vêm logo antes das da 012 (Fase 9, R38)
    phase_3_end = REQUIRED_PORTS.index("identity_accounts")
    assert REQUIRED_PORTS[phase_3_end - len(NEW_PORTS) : phase_3_end] == NEW_PORTS
    assert {"mcp_store", "audit"} <= set(STORAGE_PORTS)
    assert REQUIRED_PORTS.index("clock") < REQUIRED_PORTS.index("mcp_cache")
    assert REQUIRED_PORTS.index("mcp_dns") < REQUIRED_PORTS.index("mcp_transports")


@pytest.mark.us2
def test_o_memory_monta_registry_e_auditoria_em_memoria_com_rede_de_verdade() -> None:
    config = McpConfig(internal_hosts=frozenset({"mcp-interno"}), allowed_hosts=frozenset({"*.exemplo.org"}))
    built = profile_for("memory").build_all(Settings(profile="memory"), {"mcp_config": config})
    assert isinstance(built["mcp_store"], InMemoryServerStore)
    assert isinstance(built["mcp_dns"], SystemDnsResolver)
    assert set(built["mcp_transports"]) == {"http", "sse"}, "stdio só no persistent (design.md)"
    assert all(isinstance(t, HttpMcpTransport) for t in built["mcp_transports"].values())
    assert isinstance(built["mcp_secrets"], EnvSecretResolver)
    assert isinstance(built["mcp_cache"], InMemoryDiscoveryCache)
    assert isinstance(built["audit"], InMemoryAuditLog)


@pytest.mark.us2
def test_o_persistent_monta_registry_e_auditoria_no_postgres_e_oferece_stdio() -> None:
    settings = Settings(profile="persistent", database_url=DSN)
    built = profile_for("persistent").build_all(settings, {"assistants_config": _config(None)})
    assert isinstance(built["mcp_store"], PostgresServerStore)
    assert isinstance(built["audit"], PostgresAuditLog)
    assert set(built["mcp_transports"]) == {"http", "sse", "stdio"}
    assert isinstance(built["mcp_transports"]["stdio"], StdioMcpTransport)
    assert isinstance(built["mcp_secrets"], EnvSecretResolver)


@pytest.mark.us2
def test_o_test_monta_um_transporte_programado_sem_servidores_e_nada_de_rede() -> None:
    built = profile_for("test").build_all(Settings(profile="test"))
    transports = built["mcp_transports"]
    assert set(transports) == {"http", "sse", "stdio"}
    (transport,) = {id(t): t for t in transports.values()}.values()
    assert isinstance(transport, ScriptedMcpTransport) and transport.servers == {}
    assert isinstance(built["mcp_dns"], FixedDnsResolver)
    assert isinstance(built["mcp_secrets"], InMemorySecretResolver)
    assert isinstance(built["mcp_store"], InMemoryServerStore)
    assert isinstance(built["audit"], InMemoryAuditLog)


@pytest.mark.us2
async def test_o_provider_do_test_responde_direto_como_controller_e_faz_streaming_na_geracao() -> None:
    provider = profile_for("test").build_all(Settings(profile="test"))["providers"]["ollama"]
    response = await provider.chat([{"role": "user", "content": "oi"}], "qwen3:1.7b", stream=False)
    assert response["message"]["content"] == '{"action": "answer"}'
    chunks = await provider.chat([{"role": "user", "content": "oi"}], "qwen3:1.7b", stream=True)
    assert [chunk["delta"] async for chunk in chunks][:2] == ["Bras", "ília"]


# --- Fase 3 da 006: segredos dos providers e remotos nos perfis (T034; 006 research R23, ADR-020) --------------------


@pytest.mark.us3
def test_llm_secrets_vem_antes_de_providers() -> None:
    assert REQUIRED_PORTS.index("llm_secrets") < REQUIRED_PORTS.index("providers")


@pytest.mark.us3
@pytest.mark.parametrize("name", ["memory", "persistent"])
def test_memory_e_persistent_registram_os_tres_providers(name: str) -> None:
    settings = Settings(profile=name, database_url=DSN if name == "persistent" else None)
    built = profile_for(name).build_all(settings, {"assistants_config": _config(None)})
    assert isinstance(built["llm_secrets"], LlmEnvSecretResolver)
    providers = built["providers"]
    assert set(providers) == {"ollama", "openai", "openrouter"}
    assert isinstance(providers["ollama"], OllamaProvider)
    assert isinstance(providers["openai"], OpenAIProvider)
    assert isinstance(providers["openrouter"], OpenRouterProvider)
    assert all(provider.name == key for key, provider in providers.items())


@pytest.mark.us3
def test_o_test_mantem_so_o_provider_simulado_e_segredos_em_memoria() -> None:
    built = profile_for("test").build_all(Settings(profile="test"))
    assert set(built["providers"]) == {"ollama"}
    assert isinstance(built["providers"]["ollama"], ScriptedProvider)
    assert isinstance(built["llm_secrets"], LlmInMemorySecretResolver)


@pytest.mark.us3
async def test_remoto_sem_credencial_no_memory_relata_a_falta_sem_rede() -> None:
    built = profile_for("memory").build_all(
        Settings(), {"assistants_config": _config(None)}, overrides={"llm_secrets": LlmInMemorySecretResolver()}
    )
    result = await built["providers"]["openrouter"].probe("qwen/qwen3-8b")
    assert not result.available
    assert result.detail == "sem credencial: defina AI_CORE_OPENROUTER_API_KEY"


@pytest.mark.us3
def test_llm_secrets_pode_ser_trocada() -> None:
    assert "llm_secrets" not in NOT_OVERRIDABLE
    segredos = LlmInMemorySecretResolver({"AI_CORE_OPENAI_API_KEY": "sk-x"})
    built = profile_for("test").build_all(Settings(profile="test"), overrides={"llm_secrets": segredos})
    assert built["llm_secrets"] is segredos
