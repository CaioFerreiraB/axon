"""Perfis de adapters (specs/011-core-bootstrap/contracts/profiles.md).

Um perfil é o mapeamento porta → adapter de um ambiente. A lista de portas exigidas é **dado**: validar um perfil é
conferir que nenhuma ficou sem fábrica, e isso acontece antes da primeira etapa do boot (FR-004, research R6).

Cada fábrica recebe a configuração **e as partes já construídas**, na ordem da lista: as de armazenamento do perfil
`persistent` precisam do pool, e a chave de desenvolvimento precisa do relógio e do grupo de administração (R12).
Nenhum perfil aceita requisição sem credencial (FR-015): a autenticação é a da 003 nos três.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import httpx
from psycopg_pool import AsyncConnectionPool

from ai_core.assistants.adapters.api_keys_postgres import PostgresApiKeyStore
from ai_core.assistants.adapters.assistants_postgres import PostgresUserAssistantStore
from ai_core.assistants.adapters.memory import (
    DisabledOidcVerifier,
    InMemoryApiKeyStore,
    InMemoryUserAssistantStore,
    StaticOidcVerifier,
)
from ai_core.assistants.adapters.oidc import HttpJwksSource, JwksOidcVerifier
from ai_core.assistants.api import ApiKeyInfo
from ai_core.assistants.domain.access import OidcAudiences
from ai_core.assistants.domain.keys import ApiKeyRecord, hash_key, parse_key
from ai_core.bootstrap.identity import (
    env_identity_secrets,
    google_upstream,
    memory_identity_ports,
    postgres_identity_ports,
    seeded_identity_secrets,
    simulated_upstream,
)
from ai_core.bootstrap.settings import (
    MEMORY_PROFILE,
    PERSISTENT_PROFILE,
    TEST_PROFILE,
    ConfigurationError,
    Settings,
)
from ai_core.capabilities.adapters.audit_postgres import PostgresAuditLog
from ai_core.capabilities.adapters.memory import InMemoryAuditLog
from ai_core.graph.adapters.clock import FixedClock, SystemClock
from ai_core.http.adapters.conversations_memory import InMemoryConversationStore
from ai_core.http.adapters.conversations_postgres import PostgresConversationStore
from ai_core.http.adapters.development import SequentialRequestIds, Uuid4RequestIds
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

DEFAULT_PUBLIC_AUDIENCE: Final = OidcAudiences().public
"""Audiência do chat quando `AI_CORE_OIDC_AUDIENCE` não a define (ADR-031)."""

REQUIRED_PORTS: Final = (
    "clock",
    "trace",
    "llm_secrets",
    "providers",
    "pack_source",
    "request_ids",
    "conversation_ids",
    "database",
    "api_keys",
    "oidc",
    "user_assistants",
    "conversations",
    "mcp_store",
    "mcp_dns",
    "mcp_transports",
    "mcp_secrets",
    "mcp_cache",
    "audit",
    "identity_accounts",
    "identity_grants",
    "identity_keys",
    "identity_settings",
    "identity_attempts",
    "identity_secrets",
    "identity_upstream",
)
"""Portas secundárias que um perfil precisa atender, **na ordem de construção**. Acrescentar uma porta é acrescentar
uma linha aqui. As seis depois de `oidc` são as da 007 e da 004 (Fase 3, research R22); `llm_secrets` vem antes de
`providers`, cuja fábrica a usa (006 research R23, ADR-020); as sete últimas são as da 012 (Fase 9, R38) — a
`identity_upstream` usa a `identity_secrets`."""

STORAGE_PORTS: Final = (
    "api_keys",
    "user_assistants",
    "conversations",
    "mcp_store",
    "audit",
    "identity_accounts",
    "identity_grants",
    "identity_keys",
    "identity_settings",
)
"""As portas construídas sobre `database`. Fora do laço do servidor, são refeitas sobre um pool temporário (R13)."""

FIXED_TIME: Final = datetime(2026, 1, 1, 12, tzinfo=UTC)
"""Instante do relógio fixo do perfil de teste: torna verificáveis a data de referência e o campo `created`."""

# --- credenciais do perfil `test`, exportadas para as suítes (FR-015) -------------------------------------------------

TEST_SUBJECT: Final = "user:test"
TEST_ADMIN_GROUP: Final = "admin"
"""Grupo da chave de teste. Administra quem declarar `api_keys: {admin_group: admin}` no `assistants.yaml`."""
TEST_OIDC_TOKEN: Final = "token-oidc-de-teste"
"""Credencial da superfície pública (`/v1`): `Authorization: Bearer <TEST_OIDC_TOKEN>`."""
TEST_API_KEY: Final = "aic_7e57c0de00000001_chave-de-teste"
"""Credencial da superfície privada (`/private/v1`): `Authorization: Bearer <TEST_API_KEY>`."""

DEV_SUBJECT: Final = "user:dev"
"""Dono da chave de desenvolvimento do perfil `memory` (`AI_CORE_DEV_API_KEY`)."""

NO_CREDENTIALS_WARNING: Final = (
    "ATENÇÃO: perfil 'memory' sem AI_CORE_DEV_API_KEY nem AI_CORE_OIDC_ISSUER — toda credencial será recusada (401). "
    "Defina uma das duas para conversar com a plataforma."
)
"""Falha fechada por falta de configuração é o comportamento certo, mas sem aviso parece defeito (spec, Edge Cases)."""

Factory = Callable[[Settings, Mapping[str, Any]], Any]
"""Configuração e partes já construídas → adapter."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Profile:
    """Uma fábrica por porta exigida. O relógio é **um objeto só** para todos os módulos com porta de tempo."""

    name: str
    factories: Mapping[str, Factory]

    def build(self, port: str, settings: Settings, parts: Mapping[str, Any] | None = None) -> Any:
        return self.factories[port](settings, parts or {})

    def build_all(
        self,
        settings: Settings,
        parts: Mapping[str, Any] | None = None,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Constrói as portas exigidas na ordem da lista; cada fábrica vê `parts` e as portas anteriores.

        `overrides`: porta → adapter que substitui a fábrica — a troca que as suítes usam (R31). As fábricas seguintes
        enxergam o valor trocado.
        """
        chosen = check_overrides(overrides or {})
        built = dict(parts or {})
        for port in REQUIRED_PORTS:
            built[port] = chosen[port] if port in chosen else self.build(port, settings, built)
        return {port: built[port] for port in REQUIRED_PORTS}


NOT_OVERRIDABLE: Final = frozenset({"database", *STORAGE_PORTS})
"""As sessões de armazenamento reconstroem estas portas pelas fábricas do perfil (R13): uma troca nelas seria ignorada
em silêncio no `persistent`, então é recusada."""


def check_overrides(overrides: Mapping[str, Any]) -> Mapping[str, Any]:
    """Recusa troca de porta desconhecida ou de armazenamento, nomeando a porta."""
    unknown = sorted(port for port in overrides if port not in REQUIRED_PORTS)
    if unknown:
        raise ConfigurationError(f"troca de porta desconhecida: {', '.join(unknown)}")
    storage = sorted(port for port in overrides if port in NOT_OVERRIDABLE)
    if storage:
        raise ConfigurationError(f"porta de armazenamento não pode ser trocada: {', '.join(storage)}")
    return overrides


def lacks_credentials(settings: Settings) -> bool:
    """O `memory` sem chave de desenvolvimento nem OIDC sobe, mas recusa toda credencial — e o boot precisa dizer."""
    return settings.profile == MEMORY_PROFILE and settings.dev_api_key is None and settings.oidc_issuer is None


# --- fábricas compartilhadas ------------------------------------------------------------------------------------------


def _trace(settings: Settings, _parts: Mapping[str, Any]) -> Any:
    return JsonlTraceBackend(settings.trace_dir) if settings.trace_dir else InMemoryTraceBackend()


def _providers(settings: Settings, parts: Mapping[str, Any]) -> Any:
    """O local e os remotos da 006. Remoto sem credencial fica registrado e explica a falta na saúde e na chamada, sem
    derrubar o boot (006 FR-011, ADR-020)."""
    secrets = parts["llm_secrets"]
    return {
        "ollama": OllamaProvider(base_url=settings.ollama_base_url),
        "openai": OpenAIProvider(secrets=secrets),
        "openrouter": OpenRouterProvider(secrets=secrets),
    }


def _entry_point_source(_settings: Settings, _parts: Mapping[str, Any]) -> Any:
    from ai_core.packs.adapters.entry_points import EntryPointPackSource

    return EntryPointPackSource()


def _oidc(settings: Settings, parts: Mapping[str, Any]) -> Any:
    """JWKS do emissor configurado; sem emissor, a superfície pública recusa toda credencial (falha fechada)."""
    if settings.oidc_issuer is None or settings.oidc_audience is None:
        return DisabledOidcVerifier()
    source = HttpJwksSource(
        issuer=settings.oidc_issuer,
        client=httpx.AsyncClient(timeout=10.0),
        clock=parts["clock"],
        jwks_url=settings.oidc_jwks_url,
    )
    return JwksOidcVerifier(issuer=settings.oidc_issuer, source=source)


def _seeded_keys(*keys: tuple[str, str, Collection[str], str]) -> Callable[[Settings, Mapping[str, Any]], Any]:
    def build(_settings: Settings, parts: Mapping[str, Any]) -> Any:
        store = InMemoryApiKeyStore()
        for plaintext, subject, groups, label in keys:
            store.seed(_record(plaintext, subject=subject, groups=groups, label=label, at=parts["clock"].now()))
        return store

    return build


def _record(plaintext: str, *, subject: str, groups: Collection[str], label: str, at: datetime) -> ApiKeyRecord:
    key_id = parse_key(plaintext)
    if key_id is None:  # pragma: no cover — a configuração já recusou (settings.py)
        raise ConfigurationError("chave semeada fora do formato aic_<16 hex>_<…>")
    info = ApiKeyInfo(key_id=key_id, subject=subject, groups=frozenset(groups), label=label, created_at=at)
    return ApiKeyRecord(info=info, key_hash=hash_key(plaintext))


def _dev_keys(settings: Settings, parts: Mapping[str, Any]) -> Any:
    """Chaves em memória, com a de desenvolvimento semeada no grupo de administração do `assistants.yaml`."""
    if settings.dev_api_key is None:
        return InMemoryApiKeyStore()
    config = parts.get("assistants_config")
    admin_group = getattr(config, "admin_group", None)
    groups = (admin_group,) if admin_group else ()
    return _seeded_keys((settings.dev_api_key, DEV_SUBJECT, groups, "desenvolvimento"))(settings, parts)


# --- perfis -----------------------------------------------------------------------------------------------------------


CONTROLLER_ANSWER: Final = '{"action": "answer"}'
"""O que o provider simulado do perfil `test` responde sem streaming: como controller, responde direto — um Assistant
`agentic` funciona sem configuração extra (clarificação 2 de 2026-10-02). A suíte que quer um roteiro troca a porta."""


def _http_transports(_settings: Settings, parts: Mapping[str, Any]) -> dict[str, Any]:
    """`http` e `sse` com a política de rede da 007: os hosts internos e a allowlist vêm do arquivo do operador, lido
    na etapa de configuração (R23); sem arquivo, nenhum host interno e qualquer host público."""
    config: McpConfig = parts.get("mcp_config") or McpConfig()
    transport = HttpMcpTransport(
        dns=parts["mcp_dns"], internal_hosts=config.internal_hosts, allowed_hosts=config.allowed_hosts
    )
    return {"http": transport, "sse": transport}


def _all_transports(settings: Settings, parts: Mapping[str, Any]) -> dict[str, Any]:
    """Os de rede e o `stdio` — só no `persistent`, como o `design.md` determina."""
    return {**_http_transports(settings, parts), "stdio": StdioMcpTransport()}


def _scripted_transports(_settings: Settings, _parts: Mapping[str, Any]) -> dict[str, Any]:
    """Um transporte programado, sem servidores, para os três tipos: nada fala com rede (FR-014)."""
    transport = ScriptedMcpTransport()
    return {"http": transport, "sse": transport, "stdio": transport}


def _memory_profile() -> Profile:
    return Profile(
        name=MEMORY_PROFILE,
        factories={
            "clock": lambda _s, _p: SystemClock(),
            "trace": _trace,
            "llm_secrets": lambda _s, _p: LlmEnvSecretResolver(),
            "providers": _providers,
            "pack_source": _entry_point_source,
            "request_ids": lambda _s, _p: Uuid4RequestIds(),
            "conversation_ids": lambda _s, _p: Uuid4RequestIds(),
            "database": lambda _s, _p: None,
            "api_keys": _dev_keys,
            "oidc": _oidc,
            "user_assistants": lambda _s, _p: InMemoryUserAssistantStore(),
            "conversations": lambda _s, _p: InMemoryConversationStore(),
            "mcp_store": lambda _s, _p: InMemoryServerStore(),
            "mcp_dns": lambda _s, _p: SystemDnsResolver(),
            "mcp_transports": _http_transports,
            "mcp_secrets": lambda _s, _p: EnvSecretResolver(),
            "mcp_cache": lambda _s, p: InMemoryDiscoveryCache(p["clock"]),
            "audit": lambda _s, _p: InMemoryAuditLog(),
            **memory_identity_ports(),
            "identity_secrets": env_identity_secrets,
            "identity_upstream": google_upstream,
        },
    )


def _pool(settings: Settings, _parts: Mapping[str, Any]) -> Any:
    """Criado **fechado**: o pool pertence ao laço em que abre, e o boot roda noutro laço que o servidor (R13)."""
    if settings.database_url is None:  # pragma: no cover — a configuração já recusou (settings.py)
        raise ConfigurationError("AI_CORE_DATABASE_URL: obrigatória no perfil 'persistent'")
    return AsyncConnectionPool(settings.database_url, open=False, min_size=1, max_size=10, name="ai-core")


def _persistent_profile() -> Profile:
    return Profile(
        name=PERSISTENT_PROFILE,
        factories={
            "clock": lambda _s, _p: SystemClock(),
            "trace": _trace,
            "llm_secrets": lambda _s, _p: LlmEnvSecretResolver(),
            "providers": _providers,
            "pack_source": _entry_point_source,
            "request_ids": lambda _s, _p: Uuid4RequestIds(),
            "conversation_ids": lambda _s, _p: Uuid4RequestIds(),
            "database": _pool,
            "api_keys": lambda _s, p: PostgresApiKeyStore(p["database"]),
            "oidc": _oidc,
            "user_assistants": lambda _s, p: PostgresUserAssistantStore(p["database"]),
            "conversations": lambda _s, p: PostgresConversationStore(p["database"]),
            "mcp_store": lambda _s, p: PostgresServerStore(p["database"]),
            "mcp_dns": lambda _s, _p: SystemDnsResolver(),
            "mcp_transports": _all_transports,
            "mcp_secrets": lambda _s, _p: EnvSecretResolver(),
            "mcp_cache": lambda _s, p: InMemoryDiscoveryCache(p["clock"]),
            "audit": lambda _s, p: PostgresAuditLog(p["database"]),
            **postgres_identity_ports(),
            "identity_secrets": env_identity_secrets,
            "identity_upstream": google_upstream,
        },
    )


def _test_claims(settings: Settings) -> dict[str, object]:
    """Válidas no instante do relógio fixo, com as claims que a configuração manda ler."""
    return {
        settings.oidc_subject_claim: TEST_SUBJECT.removeprefix("user:"),
        settings.oidc_groups_claim: [TEST_ADMIN_GROUP],
        "aud": settings.oidc_audience or DEFAULT_PUBLIC_AUDIENCE,
        "iat": int(FIXED_TIME.timestamp()),
        "exp": int((FIXED_TIME + timedelta(days=1)).timestamp()),
    }


def _test_profile() -> Profile:
    return Profile(
        name=TEST_PROFILE,
        factories={
            "clock": lambda _s, _p: FixedClock(FIXED_TIME, readings=[0.0, 0.25]),
            "trace": lambda _s, _p: InMemoryTraceBackend(),
            "llm_secrets": lambda _s, _p: LlmInMemorySecretResolver(),
            "providers": lambda _s, _p: {
                "ollama": ScriptedProvider(name="ollama", content=CONTROLLER_ANSWER, deltas=("Bras", "ília"))
            },
            "pack_source": _entry_point_source,
            "request_ids": lambda _s, _p: SequentialRequestIds(),
            "conversation_ids": lambda _s, _p: SequentialRequestIds(prefix="t"),
            "database": lambda _s, _p: None,
            "api_keys": _seeded_keys((TEST_API_KEY, TEST_SUBJECT, (TEST_ADMIN_GROUP,), "teste")),
            "oidc": lambda s, _p: StaticOidcVerifier({TEST_OIDC_TOKEN: _test_claims(s)}),
            "user_assistants": lambda _s, _p: InMemoryUserAssistantStore(),
            "conversations": lambda _s, _p: InMemoryConversationStore(),
            "mcp_store": lambda _s, _p: InMemoryServerStore(),
            "mcp_dns": lambda _s, _p: FixedDnsResolver(),
            "mcp_transports": _scripted_transports,
            "mcp_secrets": lambda _s, _p: InMemorySecretResolver(),
            "mcp_cache": lambda _s, p: InMemoryDiscoveryCache(p["clock"]),
            "audit": lambda _s, _p: InMemoryAuditLog(),
            **memory_identity_ports(),
            "identity_secrets": seeded_identity_secrets,
            "identity_upstream": simulated_upstream,
        },
    )


PROFILES: Final[Mapping[str, Callable[[], Profile]]] = {
    MEMORY_PROFILE: _memory_profile,
    PERSISTENT_PROFILE: _persistent_profile,
    TEST_PROFILE: _test_profile,
}


def profile_for(name: str) -> Profile:
    """Perfil pelo nome, já validado. Perfil desconhecido ou incompleto é recusado antes do boot."""
    try:
        build = PROFILES[name]
    except KeyError:
        known = ", ".join(sorted(PROFILES))
        raise ConfigurationError(f"perfil '{name}' não existe; disponíveis: {known}") from None
    return validate(build())


def validate(profile: Profile) -> Profile:
    """Recusa perfil a que falte fábrica para alguma porta exigida, nomeando a porta (FR-004)."""
    missing = [port for port in REQUIRED_PORTS if port not in profile.factories]
    if missing:
        raise ConfigurationError(f"perfil '{profile.name}' não atende a(s) porta(s): {', '.join(missing)}")
    return profile
