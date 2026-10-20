"""Uso, preços, destinos do trace e sobreposições na composition root (Fase 9; research R36, R38, R40, R41).

As portas por perfil — memória no `memory` e no `test`, Postgres no `persistent` (schemas `observability` e
`assistants`, ADR-015) — e a montagem dos destinos do trace da 009 (ADR-034): o `UsageDestination`, com a origem do
processo (`production`, ou `evaluation` no `axon eval run`), e o `LangfuseDestination`, que o `DestinationService`
liga e desliga pelos ajustes efetivos (instalação > console > padrão, ADR-033). O `TraceService` lê a captura de
conteúdo do mesmo serviço, a cada evento e sem I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from axon_ai.assistants.adapters.memory import InMemorySystemOverrideStore
from axon_ai.assistants.adapters.overrides_postgres import PostgresSystemOverrideStore
from axon_ai.bootstrap import identity as identity_parts
from axon_ai.bootstrap.settings import PERSISTENT_PROFILE, Settings
from axon_ai.observability.adapters.cipher import AesGcmCipher
from axon_ai.observability.adapters.langfuse import LangfuseDestination, OtelLangfuseTransport
from axon_ai.observability.adapters.memory import (
    InMemoryDestinationSettingsStore,
    InMemoryPriceStore,
    InMemoryUsageStore,
    RecordingLangfuseTransport,
)
from axon_ai.observability.adapters.postgres import (
    PostgresDestinationSettingsStore,
    PostgresPriceStore,
    PostgresUsageStore,
)
from axon_ai.observability.adapters.usage import UsageDestination
from axon_ai.observability.domain.settings import InstallationDestinations, LangfuseCredentials
from axon_ai.observability.ports import Origin
from axon_ai.observability.service import DestinationService, UsageService

PRODUCTION: Final[Origin] = "production"
EVALUATION: Final[Origin] = "evaluation"

USAGE_FLUSH_INTERVAL: Final = 2.0
"""Segundos entre as gravações do lote de uso (009 R30): o buffer nunca espera o banco no caminho de quem emite."""
USAGE_PURGE_INTERVAL: Final = 86_400.0
"""A retenção do uso (`AXON_USAGE_RETENTION_DAYS`) roda uma vez por dia."""


# --- fábricas das portas (R38) ----------------------------------------------------------------------------------------


def memory_ports() -> dict[str, Any]:
    """Sobreposições da 003 e armazenamentos da 009 em memória: `memory` e `test`."""
    return {
        "system_overrides": lambda _s, _p: InMemorySystemOverrideStore(),
        "usage_store": lambda _s, _p: InMemoryUsageStore(),
        "price_store": lambda _s, _p: InMemoryPriceStore(),
        "destination_settings": lambda _s, _p: InMemoryDestinationSettingsStore(),
    }


def postgres_ports() -> dict[str, Any]:
    return {
        "system_overrides": lambda _s, p: PostgresSystemOverrideStore(p["database"]),
        "usage_store": lambda _s, p: PostgresUsageStore(p["database"]),
        "price_store": lambda _s, p: PostgresPriceStore(p["database"]),
        "destination_settings": lambda _s, p: PostgresDestinationSettingsStore(p["database"]),
    }


def otel_transport(_settings: Settings, _parts: Mapping[str, Any]) -> Any:
    """OTLP/HTTP de verdade (009 R32); sem credenciais, não envia nada."""
    return OtelLangfuseTransport()


def recording_transport(_settings: Settings, _parts: Mapping[str, Any]) -> Any:
    """O `test` nunca sai para a rede: o transporte só guarda o que enviaria (011 FR-014)."""
    return RecordingLangfuseTransport()


# --- montagem (R40) ---------------------------------------------------------------------------------------------------


def installation(settings: Settings) -> InstallationDestinations:
    """O que a instalação define por variável — já validado em `Settings` (o grupo do Langfuse é tudo ou nada)."""
    credentials = None
    if settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key:
        credentials = LangfuseCredentials(
            host=settings.langfuse_host.rstrip("/"),
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
        )
    return InstallationDestinations(langfuse=credentials, capture=settings.langfuse_capture_content)


def cipher(settings: Settings, parts: dict[str, Any]) -> AesGcmCipher | None:
    """O segredo do Langfuse gravado pela console é selado com a chave mestra (ADR-033). No `persistent` sem ela, não
    há cifra: gravar o segredo responde `master_key_missing` e o resto funciona; no `memory`, a chave aleatória do
    processo; no `test`, a fixa."""
    if settings.profile == PERSISTENT_PROFILE and settings.master_key is None:
        return None
    return AesGcmCipher(identity_parts.shared_master_key(parts))


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceParts:
    usage_destination: UsageDestination
    langfuse_destination: LangfuseDestination
    destinations: DestinationService
    usage: UsageService


def trace_parts(parts: dict[str, Any]) -> TraceParts:
    """Os destinos e os serviços da 009 sobre as portas da plataforma. A origem vem do `platform(origin=…)`."""
    settings: Settings = parts["settings"]
    clock = parts["clock"]
    usage_destination = UsageDestination(
        store=parts["usage_store"], origin=parts.get("origin", PRODUCTION), clock=clock
    )
    langfuse_destination = LangfuseDestination(parts["langfuse_transport"], clock=clock.now)
    destinations = DestinationService(
        store=parts["destination_settings"],
        cipher=cipher(settings, parts),
        installation=installation(settings),
        transport=parts["langfuse_transport"],
        langfuse=langfuse_destination,
        usage=usage_destination,
        clock=clock,
    )
    usage = UsageService(
        store=parts["usage_store"],
        prices=parts["price_store"],
        clock=clock,
        default_timezone=settings.usage_timezone,
    )
    return TraceParts(
        usage_destination=usage_destination,
        langfuse_destination=langfuse_destination,
        destinations=destinations,
        usage=usage,
    )
