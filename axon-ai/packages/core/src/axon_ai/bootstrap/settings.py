"""Configuração do operador (specs/011-core-bootstrap/contracts/configuration.md).

A validação é pura e acontece **antes** da primeira etapa do boot: erro de configuração nomeia o campo e impede o
serviço de subir (FR-001, SC-002).
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from axon_ai.assistants.domain.keys import parse_key
from axon_ai.observability.api import InvalidField
from axon_ai.observability.domain.settings import check_host

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
DEFAULT_RAG_CANDIDATES: Final = 20
DEFAULT_RAG_PASSAGES: Final = 5
"""Os defaults de `RagSettings` (005, research R44). Sem limiar por default: a 105 calibra (princípio X)."""
DEFAULT_MAX_EXECUTIONS: Final = 2
DEFAULT_QUEUE_SIZE: Final = 8
DEFAULT_QUEUE_WAIT_MS: Final = 60_000
"""Admissão da API (008 FR-016, research R36): valores provisórios, medidos no hardware alvo (008 quickstart)."""
MAX_EXECUTIONS_RANGE: Final = (1, 64)
QUEUE_SIZE_RANGE: Final = (0, 1_000)
QUEUE_WAIT_RANGE: Final = (1, 600_000)
"""As faixas de `AdmissionLimits` (008), repetidas aqui para que o erro nomeie a variável."""

DEFAULT_DISPLAY_NAME: Final = "Axon"
"""Nome da instalação nas páginas do provedor e na console quando ela não define o seu (012 FR-023, ADR-038)."""
MASTER_KEY_BYTES: Final = 32
DEFAULT_USAGE_TIMEZONE: Final = "UTC"
DEFAULT_USAGE_RETENTION_DAYS: Final = 400
MIN_USAGE_RETENTION_DAYS: Final = 30
"""Uso por dia (009 US5): fuso padrão do relatório e retenção das linhas brutas (research R36)."""
_LOCAL_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1"})

PREFIX: Final = "AXON_"
LEGACY_PREFIX: Final = "AI_CORE_"
"""O prefixo antigo (ADR-037): presente no ambiente, recusa a configuração em vez de ser ignorado (FR-025)."""


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
    """Arquivo de servidores MCP do operador (formato da 007). As credenciais (`AXON_MCP_SECRET_<REF>`) **não**
    passam por aqui: a 007 as lê só ao montar a operação (R27)."""
    mcp_discovery_ttl: float = DEFAULT_MCP_DISCOVERY_TTL
    tool_timeout_ms: int = DEFAULT_TOOL_TIMEOUT_MS
    tool_max_response_bytes: int = DEFAULT_TOOL_MAX_RESPONSE_BYTES
    rag_candidates: int = DEFAULT_RAG_CANDIDATES
    rag_passages: int = DEFAULT_RAG_PASSAGES
    rag_min_score: float | None = None
    """O limiar do portão do `rag_first` (005 FR-007): sem valor, só a ausência de resultado escala."""
    max_executions: int = DEFAULT_MAX_EXECUTIONS
    queue_size: int = DEFAULT_QUEUE_SIZE
    """0 = sem fila: com as vagas cheias, o pedido é recusado na hora (008 FR-017)."""
    queue_wait_ms: int = DEFAULT_QUEUE_WAIT_MS
    identity_enabled: bool = False
    """Liga o provedor de identidade da plataforma (012, ADR-030)."""
    public_url: str | None = None
    """Endereço público da instalação: o emissor dos tokens (012 FR-019)."""
    identity_clients_file: Path | None = None
    master_key: bytes | None = field(default=None, repr=False)
    """Segredo: 32 bytes que selam a chave de assinatura (ADR-033). Nunca em log, relatório ou mensagem."""
    display_name: str = DEFAULT_DISPLAY_NAME
    logo_file: Path | None = None
    trusted_proxies: tuple[str, ...] = ()
    cookie_secure: bool | None = None
    """Ausente: ligado quando `public_url` é `https` (012 R5)."""
    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = field(default=None, repr=False)
    """Segredo. O grupo `AXON_LANGFUSE_HOST|PUBLIC_KEY|SECRET_KEY` é tudo ou nada; definido, prevalece sobre a
    console, que o mostra somente leitura (ADR-033)."""
    langfuse_capture_content: bool | None = None
    """`AXON_LANGFUSE_CAPTURE_CONTENT`: definida, prevalece sobre a console (ADR-034)."""
    usage_timezone: str = DEFAULT_USAGE_TIMEZONE
    usage_retention_days: int = DEFAULT_USAGE_RETENTION_DAYS

    @property
    def secure_cookie(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return (self.public_url or "").startswith("https://")

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
                    f"{PREFIX}DEV_API_KEY: não vale no perfil '{PERSISTENT_PROFILE}' — emita chaves com `axon keys`"
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
        # As regras de `RagSettings` (005), aqui para que o erro nomeie a variável.
        if self.rag_candidates < 1:
            raise ConfigurationError(f"{PREFIX}RAG_CANDIDATES: precisa ser ao menos 1: {self.rag_candidates}")
        if self.rag_passages < 1:
            raise ConfigurationError(f"{PREFIX}RAG_PASSAGES: precisa ser ao menos 1: {self.rag_passages}")
        if self.rag_min_score is not None and not 0.0 <= self.rag_min_score <= 1.0:  # NaN também cai aqui
            raise ConfigurationError(f"{PREFIX}RAG_MIN_SCORE: precisa estar entre 0 e 1: {self.rag_min_score}")
        _within(f"{PREFIX}MAX_EXECUTIONS", self.max_executions, MAX_EXECUTIONS_RANGE)
        _within(f"{PREFIX}QUEUE_SIZE", self.queue_size, QUEUE_SIZE_RANGE)
        _within(f"{PREFIX}QUEUE_WAIT_MS", self.queue_wait_ms, QUEUE_WAIT_RANGE)
        self._check_identity()
        self._check_observability()

    def _check_observability(self) -> None:
        """Fase 9 (research R36): o grupo do Langfuse, o fuso e a retenção do uso. O segredo nunca aparece."""
        group = {
            f"{PREFIX}LANGFUSE_HOST": self.langfuse_host,
            f"{PREFIX}LANGFUSE_PUBLIC_KEY": self.langfuse_public_key,
            f"{PREFIX}LANGFUSE_SECRET_KEY": self.langfuse_secret_key,
        }
        missing = [name for name, value in group.items() if not value]
        if 0 < len(missing) < len(group):
            raise ConfigurationError(
                f"{missing[0]}: o grupo {PREFIX}LANGFUSE_HOST, _PUBLIC_KEY e _SECRET_KEY é tudo ou nada"
            )
        if self.langfuse_host:
            try:
                check_host(self.langfuse_host)
            except InvalidField as error:
                raise ConfigurationError(f"{PREFIX}LANGFUSE_HOST: {str(error).removeprefix('host: ')}") from None
        try:
            ZoneInfo(self.usage_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ConfigurationError(
                f"{PREFIX}USAGE_TIMEZONE: fuso IANA desconhecido: {self.usage_timezone!r}"
            ) from None
        if self.usage_retention_days < MIN_USAGE_RETENTION_DAYS:
            raise ConfigurationError(
                f"{PREFIX}USAGE_RETENTION_DAYS: precisa ser ao menos {MIN_USAGE_RETENTION_DAYS}: "
                f"{self.usage_retention_days}"
            )

    def _check_identity(self) -> None:
        """Fase 9 (research R36): param o boot e nomeiam a variável; a chave mestra nunca aparece."""
        if self.master_key is not None and len(self.master_key) != MASTER_KEY_BYTES:
            raise ConfigurationError(f"{PREFIX}MASTER_KEY: precisa ter {MASTER_KEY_BYTES} bytes em base64")
        if self.public_url is not None:
            _check_public_url(self.public_url)
        for entry in self.trusted_proxies:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError:
                raise ConfigurationError(f"{PREFIX}TRUSTED_PROXIES: não é IP nem rede: {entry!r}") from None
        if not self.display_name.strip():
            raise ConfigurationError(f"{PREFIX}DISPLAY_NAME: não pode ser vazio")
        if not self.identity_enabled:
            return
        if self.oidc_issuer:
            raise ConfigurationError(
                f"{PREFIX}IDENTITY_ENABLED: não combina com {PREFIX}OIDC_ISSUER — a plataforma confia num emissor só "
                "(ADR-030)"
            )
        if self.public_url is None:
            raise ConfigurationError(f"{PREFIX}PUBLIC_URL: obrigatório com {PREFIX}IDENTITY_ENABLED")
        if self.identity_clients_file is None and self.profile != TEST_PROFILE:
            raise ConfigurationError(f"{PREFIX}IDENTITY_CLIENTS_FILE: obrigatório com {PREFIX}IDENTITY_ENABLED")
        if self.profile == PERSISTENT_PROFILE and self.master_key is None:
            raise ConfigurationError(
                f"{PREFIX}MASTER_KEY: obrigatória no perfil '{PERSISTENT_PROFILE}' com a identidade ligada (ADR-033)"
            )


def _check_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment:
        raise ConfigurationError(f"{PREFIX}PUBLIC_URL: precisa ser uma URL http(s) absoluta, sem query: {url!r}")
    if parts.scheme == "http" and parts.hostname not in _LOCAL_HOSTS:
        raise ConfigurationError(f"{PREFIX}PUBLIC_URL: precisa ser https (http só para localhost): {url!r}")


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
    """Configuração a partir das variáveis `AXON_*` (contracts/configuration.md)."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = dict(environ if environ is not None else os.environ)

    def load(self) -> Settings:
        self._refuse_legacy()
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
            rag_candidates=self._int("RAG_CANDIDATES", DEFAULT_RAG_CANDIDATES),
            rag_passages=self._int("RAG_PASSAGES", DEFAULT_RAG_PASSAGES),
            rag_min_score=self._optional_float("RAG_MIN_SCORE"),
            max_executions=self._int("MAX_EXECUTIONS", DEFAULT_MAX_EXECUTIONS),
            queue_size=self._int("QUEUE_SIZE", DEFAULT_QUEUE_SIZE),
            queue_wait_ms=self._int("QUEUE_WAIT_MS", DEFAULT_QUEUE_WAIT_MS),
            identity_enabled=self._bool("IDENTITY_ENABLED", False),
            public_url=self._optional("PUBLIC_URL"),
            identity_clients_file=self._path("IDENTITY_CLIENTS_FILE"),
            master_key=self._master_key(),
            display_name=self._text("DISPLAY_NAME", DEFAULT_DISPLAY_NAME),
            logo_file=self._path("LOGO_FILE"),
            trusted_proxies=tuple(
                entry.strip() for entry in self._text("TRUSTED_PROXIES", "").split(",") if entry.strip()
            ),
            cookie_secure=self._optional_bool("COOKIE_SECURE"),
            langfuse_host=self._optional("LANGFUSE_HOST"),
            langfuse_public_key=self._optional("LANGFUSE_PUBLIC_KEY"),
            langfuse_secret_key=self._optional("LANGFUSE_SECRET_KEY"),
            langfuse_capture_content=self._optional_bool("LANGFUSE_CAPTURE_CONTENT"),
            usage_timezone=self._text("USAGE_TIMEZONE", DEFAULT_USAGE_TIMEZONE),
            usage_retention_days=self._int("USAGE_RETENTION_DAYS", DEFAULT_USAGE_RETENTION_DAYS),
        )

    def _refuse_legacy(self) -> None:
        """Corte seco com diagnóstico (ADR-037, item 3; R48): o nome novo de cada variável antiga, nunca o valor."""
        legacy = sorted(name for name in self._environ if name.startswith(LEGACY_PREFIX))
        if legacy:
            lines = (f"  {name} → {PREFIX}{name.removeprefix(LEGACY_PREFIX)}" for name in legacy)
            raise ConfigurationError(
                "variáveis com o nome antigo da plataforma (ADR-037); renomeie:\n" + "\n".join(lines)
            )

    def _master_key(self) -> bytes | None:
        raw = self._optional("MASTER_KEY")
        if raw is None:
            return None
        try:
            return base64.b64decode(raw.strip(), validate=True)
        except (binascii.Error, ValueError):
            # Nunca o valor: é a chave que sela os segredos da instalação (ADR-033).
            raise ConfigurationError(f"{PREFIX}MASTER_KEY: não é base64 válido") from None

    def _bool(self, name: str, default: bool) -> bool:
        value = self._optional_bool(name)
        return default if value is None else value

    def _optional_bool(self, name: str) -> bool | None:
        raw = self._environ.get(f"{PREFIX}{name}")
        if not raw:
            return None
        if raw.strip().lower() in ("1", "true", "yes", "on"):
            return True
        if raw.strip().lower() in ("0", "false", "no", "off"):
            return False
        raise ConfigurationError(f"{PREFIX}{name}: precisa ser true ou false: {raw!r}")

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

    def _optional_float(self, name: str) -> float | None:
        raw = self._environ.get(f"{PREFIX}{name}")
        return None if not raw else self._float(name, 0.0)

    def _float(self, name: str, default: float) -> float:
        raw = self._environ.get(f"{PREFIX}{name}")
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError as error:
            raise ConfigurationError(f"{PREFIX}{name}: precisa ser um número: {raw!r}") from error
