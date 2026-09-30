"""Montagem da plataforma: **o único lugar do projeto** que instancia serviços e adapters de outros módulos.

É a exceção que o princípio XIII reserva à composition root (ADR-012). As etapas vêm de `lifecycle.py` e a ordem é a
da spec: configuração → adapters → packs → motor → validação de Assistants (003) → API. O registry MCP (007) entra na
fase dele, acrescentando uma etapa à lista (research R1).

Os serviços da 003 entram aqui com os adapters em memória, na troca atômica da passada da Fase 2 da 008 (research R13
dela); perfil persistente e autenticação real nos perfis são da Fase 2 desta spec.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from ai_core.assistants.adapters.assistants_yaml import YamlAssistantConfigSource
from ai_core.assistants.adapters.catalogs import EmptyCollectionCatalog, EmptyMcpDirectory
from ai_core.assistants.adapters.memory import (
    DisabledOidcVerifier,
    InMemoryApiKeyStore,
    InMemoryAssistantConfigSource,
    InMemoryUserAssistantStore,
)
from ai_core.assistants.adapters.rate_memory import InMemoryRateCounterStore
from ai_core.assistants.adapters.tokens import SecretsTokenGenerator
from ai_core.assistants.domain.access import OidcClaims
from ai_core.assistants.service import AccessService, AssistantsService
from ai_core.bootstrap.health import BootReportHealth
from ai_core.bootstrap.lifecycle import BootContext, BootReport, Stage, run_stages, shutdown
from ai_core.bootstrap.ports import ConfigSource
from ai_core.bootstrap.profiles import Profile, profile_for
from ai_core.bootstrap.settings import EnvConfigSource, Settings
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.service import ExecutionService
from ai_core.http.adapters.app import create_app
from ai_core.http.adapters.conversations_memory import InMemoryConversationStore
from ai_core.llm.service import ModelRoutingService
from ai_core.observability.service import TraceService
from ai_core.packs.adapters.config_yaml import YamlPackConfigSource
from ai_core.packs.adapters.memory import InMemoryPackConfigSource
from ai_core.packs.api import PackStatus
from ai_core.packs.service import PackRuntime

STAGE_CONFIGURATION = "configuration"
STAGE_ADAPTERS = "adapters"
STAGE_PACKS = "packs"
STAGE_ENGINE = "engine"
STAGE_ASSISTANTS = "assistants"
STAGE_API = "api"


@dataclass(frozen=True, slots=True, kw_only=True)
class Platform:
    """O que o boot entrega. Campos ficam vazios quando a etapa que os produz não chegou a rodar."""

    settings: Settings
    profile: Profile | None
    report: BootReport
    packs: PackRuntime | None = None
    trace: TraceService | None = None
    engine: ExecutionService | None = None
    assistants: AssistantsService | None = None
    access: AccessService | None = None
    app: FastAPI | None = None
    context: BootContext

    @property
    def ok(self) -> bool:
        return self.report.ok

    def aclose(self) -> None:
        """Libera os recursos na ordem inversa do boot (FR-013)."""
        shutdown(self.context)


def platform(*, profile: str | None = None, config: ConfigSource | None = None) -> Platform:
    """Monta a plataforma inteira. `profile` sobrepõe o da configuração — é o atalho das suítes."""
    source = config or EnvConfigSource()
    context = BootContext()
    report, context = run_stages(_stages(source, profile), context)
    parts = context.parts
    health = parts.get("health")
    if isinstance(health, BootReportHealth):
        health.report = report
    return Platform(
        settings=parts.get("settings", Settings()),
        profile=parts.get("profile"),
        report=report,
        packs=parts.get("packs"),
        trace=parts.get("trace"),
        engine=parts.get("engine"),
        assistants=parts.get("assistants"),
        access=parts.get("access"),
        app=parts.get("app"),
        context=context,
    )


def _stages(source: ConfigSource, override: str | None) -> tuple[Stage, ...]:
    """As etapas registradas. A lista é dado: acrescentar uma não toca o executor."""
    return (
        Stage(name=STAGE_CONFIGURATION, run=lambda ctx: _configuration(ctx, source, override), critical=True),
        Stage(name=STAGE_ADAPTERS, run=_adapters, critical=True),
        Stage(name=STAGE_PACKS, run=_packs, critical=False),
        Stage(name=STAGE_ENGINE, run=_engine, critical=True),
        Stage(name=STAGE_ASSISTANTS, run=_assistants, critical=False),
        Stage(name=STAGE_API, run=_api, critical=True),
    )


def _configuration(ctx: BootContext, source: ConfigSource, override: str | None) -> None:
    settings = source.load()
    if override is not None and override != settings.profile:
        settings = Settings(
            profile=override,
            packs_file=settings.packs_file,
            assistants_file=settings.assistants_file,
            ollama_base_url=settings.ollama_base_url,
            trace_dir=settings.trace_dir,
            host=settings.host,
            port=settings.port,
            shutdown_grace_seconds=settings.shutdown_grace_seconds,
        )
    ctx.parts["settings"] = settings
    # Erro de arquivo no assistants.yaml para o boot aqui; erro de um Assistant só o deixa indisponível (003 FR-011).
    source_of_assistants = (
        YamlAssistantConfigSource(settings.assistants_file)
        if settings.assistants_file is not None
        else InMemoryAssistantConfigSource({})
    )
    ctx.parts["assistants_config"] = source_of_assistants.load()


def _adapters(ctx: BootContext) -> None:
    settings: Settings = ctx.parts["settings"]
    profile = profile_for(settings.profile)
    ctx.parts["profile"] = profile
    for port in ("clock", "trace_backend", "providers", "pack_source", "authenticator", "request_ids"):
        key = "trace" if port == "trace_backend" else port
        ctx.parts[port] = profile.build(key, settings)
    ctx.parts["conversation_ids"] = profile.build("request_ids", settings)


def _packs(ctx: BootContext) -> None:
    settings: Settings = ctx.parts["settings"]
    config = (
        YamlPackConfigSource(settings.packs_file) if settings.packs_file is not None else InMemoryPackConfigSource({})
    )
    runtime = PackRuntime(ctx.parts["pack_source"], config)
    runtime.load()
    ctx.parts["packs"] = runtime

    broken = [entry for entry in runtime.entries() if entry.status is PackStatus.ERROR]
    if broken:
        # Pack em erro degrada a etapa e o boot segue: os demais packs atendem (princípio VII, SC-004).
        ctx.parts[f"{STAGE_PACKS}:degraded"] = "; ".join(f"pack '{e.name}': {e.error}" for e in broken)


def _engine(ctx: BootContext) -> None:
    clock = ctx.parts["clock"]
    backend = ctx.parts["trace_backend"]
    trace = TraceService(exporter=backend, reader=_reader_of(backend), clock=clock)
    ctx.parts["trace"] = trace

    engine = ExecutionService(
        flows=langgraph_runtime(),
        hooks=ctx.parts["packs"],
        routing=ModelRoutingService(providers=ctx.parts["providers"], trace=trace, clock=clock),
        trace=trace,
        clock=clock,
    )
    ctx.parts["engine"] = engine


def _reader_of(backend: Any) -> Any:
    """Um backend que só escreve não oferece leitura; a consulta responde explicitamente (009 research R5)."""
    return backend if hasattr(backend, "read") else None


def _assistants(ctx: BootContext) -> None:
    """Monta os serviços da 003 e valida todos os Assistants contra packs, flows, MCPs e coleções (003 FR-011).

    Assistant indisponível degrada a etapa com o motivo e o resto serve — como pack em erro (011 FR-003).
    """
    config = ctx.parts["assistants_config"]
    clock = ctx.parts["clock"]
    assistants = AssistantsService(
        config=config,
        packs=ctx.parts["packs"],
        flows=ctx.parts["engine"].flows(),
        users=InMemoryUserAssistantStore(),
        mcp=EmptyMcpDirectory(),
        collections=EmptyCollectionCatalog(),
        rate=InMemoryRateCounterStore(),
        clock=clock,
    )
    ctx.parts["assistants"] = assistants
    ctx.parts["access"] = AccessService(
        keys=InMemoryApiKeyStore(),
        oidc=DisabledOidcVerifier(),
        tokens=SecretsTokenGenerator(),
        clock=clock,
        claims=OidcClaims(),
        admin_group=config.admin_group,
    )
    report = _run(assistants.validate())
    unavailable = [status for status in report.statuses if not status.available]
    if unavailable:
        ctx.parts[f"{STAGE_ASSISTANTS}:degraded"] = "; ".join(
            f"assistant '{status.name}': {'; '.join(status.reasons)}" for status in unavailable
        )


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    """Roda uma corrotina no boot, que é síncrono — inclusive quando quem chama já está dentro de um laço de eventos
    (a suíte de um pack que monta a plataforma num teste assíncrono)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


def _api(ctx: BootContext) -> None:
    health = BootReportHealth()
    ctx.parts["health"] = health
    ctx.parts["app"] = create_app(
        engine=ctx.parts["engine"],
        authenticator=ctx.parts["authenticator"],
        grants=ctx.parts["assistants"],
        directory=ctx.parts["assistants"],
        keys=ctx.parts["access"],
        packs=ctx.parts["packs"],
        admin=ctx.parts["access"],
        conversations=InMemoryConversationStore(),
        health=health,
        request_ids=ctx.parts["request_ids"],
        conversation_ids=ctx.parts["conversation_ids"],
        clock=ctx.parts["clock"],
    )
