"""Configuração do operador (specs/011-core-bootstrap/contracts/configuration.md).

A validação é pura e acontece **antes** da primeira etapa do boot: erro de configuração nomeia o campo e impede o
serviço de subir (FR-001, SC-002).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from ai_core.assistants.domain.keys import parse_key

MEMORY_PROFILE: Final = "memory"
PERSISTENT_PROFILE: Final = "persistent"
TEST_PROFILE: Final = "test"
PROFILES: Final = (MEMORY_PROFILE, PERSISTENT_PROFILE, TEST_PROFILE)

DEFAULT_OLLAMA_BASE_URL: Final = "http://localhost:11434/v1"
DEFAULT_HOST: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8000
DEFAULT_SHUTDOWN_GRACE: Final = 10.0
DEFAULT_RETENTION_DAYS: Final = 180
DEFAULT_EXPIRY_INTERVAL: Final = 3600.0
DEFAULT_MCP_DISCOVERY_TTL: Final = 300.0
DEFAULT_TOOL_TIMEOUT_MS: Final = 30_000
DEFAULT_TOOL_MAX_RESPONSE_BYTES: Final = 16_384
TOOL_TIMEOUT_RANGE: Final = (1_000, 300_000)
TOOL_MAX_RESPONSE_RANGE: Final = (1_024, 1_048_576)
"""As faixas de `GatewayLimits` (004), repetidas aqui para que o erro nomeie a variável (FR-001, research R27)."""

PREFIX: Final = "AI_CORE_"


class ConfigurationError(ValueError):
    """Configuração inválida. A mensagem sempre nomeia o campo ou a variável."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    """O que o operador escolheu. Validada na construção."""

    profile: str = MEMORY_PROFILE
    packs_file: Path | None = None
    assistants_file: Path | None = None
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    trace_dir: Path | None = None
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    shutdown_grace_seconds: float = DEFAULT_SHUTDOWN_GRACE
    database_url: str | None = field(default=None, repr=False)
    """Segredo: nunca entra em `repr`, log, relatório ou mensagem de erro (FR-009)."""
    dev_api_key: str | None = field(default=None, repr=False)
    """Segredo: a chave de desenvolvimento do perfil `memory` (FR-015)."""
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_subject_claim: str = "sub"
    oidc_groups_claim: str = "groups"
    conversation_retention_days: int = DEFAULT_RETENTION_DAYS
    conversation_expiry_interval: float = DEFAULT_EXPIRY_INTERVAL
    mcp_file: Path | None = None
    """Arquivo de servidores MCP do operador (formato da 007). As credenciais (`AI_CORE_MCP_SECRET_<REF>`) **não**
    passam por aqui: a 007 as lê só ao montar a operação (R27)."""
    mcp_discovery_ttl: float = DEFAULT_MCP_DISCOVERY_TTL
    tool_timeout_ms: int = DEFAULT_TOOL_TIMEOUT_MS
    tool_max_response_bytes: int = DEFAULT_TOOL_MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if self.profile not in PROFILES:
            known = ", ".join(PROFILES)
            raise ConfigurationError(f"{PREFIX}PROFILE: perfil '{self.profile}' não existe; disponíveis: {known}")
        if not 1 <= self.port <= 65535:
            raise ConfigurationError(f"{PREFIX}PORT: porta fora da faixa 1-65535: {self.port}")
        if self.shutdown_grace_seconds < 0:
            raise ConfigurationError(
                f"{PREFIX}SHUTDOWN_GRACE_SECONDS: prazo não pode ser negativo: {self.shutdown_grace_seconds}"
            )
        if not self.ollama_base_url.strip():
            raise ConfigurationError(f"{PREFIX}OLLAMA_BASE_URL não pode ser vazio")
        # As mensagens abaixo nomeiam a variável e nunca repetem o valor: são segredos (FR-009).
        if self.profile == PERSISTENT_PROFILE and not self.database_url:
            raise ConfigurationError(f"{PREFIX}DATABASE_URL: obrigatória no perfil '{PERSISTENT_PROFILE}'")
        if self.dev_api_key is not None:
            if self.profile == PERSISTENT_PROFILE:
                raise ConfigurationError(
                    f"{PREFIX}DEV_API_KEY: não vale no perfil '{PERSISTENT_PROFILE}' — emita chaves com `ai-core keys`"
                )
            if parse_key(self.dev_api_key) is None:
                raise ConfigurationError(f"{PREFIX}DEV_API_KEY: precisa ter o formato aic_<16 hex>_<…>")
        if self.oidc_issuer and not self.oidc_audience:
            raise ConfigurationError(f"{PREFIX}OIDC_AUDIENCE: obrigatória quando {PREFIX}OIDC_ISSUER está definida")
        if self.conversation_retention_days < 1:
            raise ConfigurationError(f"{PREFIX}CONVERSATION_RETENTION_DAYS: precisa ser ao menos 1")
        if self.conversation_expiry_interval <= 0:
            raise ConfigurationError(f"{PREFIX}CONVERSATION_EXPIRY_INTERVAL: precisa ser positivo")
        if self.mcp_discovery_ttl <= 0:
            raise ConfigurationError(f"{PREFIX}MCP_DISCOVERY_TTL: precisa ser positivo")
        _within(f"{PREFIX}TOOL_TIMEOUT_MS", self.tool_timeout_ms, TOOL_TIMEOUT_RANGE)
        _within(f"{PREFIX}TOOL_MAX_RESPONSE_BYTES", self.tool_max_response_bytes, TOOL_MAX_RESPONSE_RANGE)


def _within(variable: str, value: int, bounds: tuple[int, int]) -> None:
    low, high = bounds
    if not low <= value <= high:
        raise ConfigurationError(f"{variable}: precisa estar entre {low} e {high}: {value}")


class InMemoryConfigSource:
    """Configuração pronta — o adapter em memória da porta."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings(profile=TEST_PROFILE)

    def load(self) -> Settings:
        return self._settings


class EnvConfigSource:
    """Configuração a partir das variáveis `AI_CORE_*` (contracts/configuration.md)."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = dict(environ if environ is not None else os.environ)

    def load(self) -> Settings:
        return Settings(
            profile=self._text("PROFILE", MEMORY_PROFILE),
            packs_file=self._path("PACKS_FILE"),
            assistants_file=self._path("ASSISTANTS_FILE"),
            ollama_base_url=self._text("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            trace_dir=self._path("TRACE_DIR"),
            host=self._text("HOST", DEFAULT_HOST),
            port=self._int("PORT", DEFAULT_PORT),
            shutdown_grace_seconds=self._float("SHUTDOWN_GRACE_SECONDS", DEFAULT_SHUTDOWN_GRACE),
            database_url=self._optional("DATABASE_URL"),
            dev_api_key=self._optional("DEV_API_KEY"),
            oidc_issuer=self._optional("OIDC_ISSUER"),
            oidc_audience=self._optional("OIDC_AUDIENCE"),
            oidc_jwks_url=self._optional("OIDC_JWKS_URL"),
            oidc_subject_claim=self._text("OIDC_SUBJECT_CLAIM", "sub"),
            oidc_groups_claim=self._text("OIDC_GROUPS_CLAIM", "groups"),
            conversation_retention_days=self._int("CONVERSATION_RETENTION_DAYS", DEFAULT_RETENTION_DAYS),
            conversation_expiry_interval=self._float("CONVERSATION_EXPIRY_INTERVAL", DEFAULT_EXPIRY_INTERVAL),
            mcp_file=self._path("MCP_FILE"),
            mcp_discovery_ttl=self._float("MCP_DISCOVERY_TTL", DEFAULT_MCP_DISCOVERY_TTL),
            tool_timeout_ms=self._int("TOOL_TIMEOUT_MS", DEFAULT_TOOL_TIMEOUT_MS),
            tool_max_response_bytes=self._int("TOOL_MAX_RESPONSE_BYTES", DEFAULT_TOOL_MAX_RESPONSE_BYTES),
        )

    def _optional(self, name: str) -> str | None:
        raw = self._environ.get(f"{PREFIX}{name}")
        return raw if raw else None

    def _text(self, name: str, default: str) -> str:
        return self._environ.get(f"{PREFIX}{name}", default)

    def _path(self, name: str) -> Path | None:
        raw = self._environ.get(f"{PREFIX}{name}")
        return Path(raw) if raw else None

    def _int(self, name: str, default: int) -> int:
        raw = self._environ.get(f"{PREFIX}{name}")
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError as error:
            raise ConfigurationError(f"{PREFIX}{name}: precisa ser um número inteiro: {raw!r}") from error

    def _float(self, name: str, default: float) -> float:
        raw = self._environ.get(f"{PREFIX}{name}")
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError as error:
            raise ConfigurationError(f"{PREFIX}{name}: precisa ser um número: {raw!r}") from error
