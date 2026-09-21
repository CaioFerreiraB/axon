"""Montagem da plataforma: **o único lugar do projeto** que instancia serviços e adapters de outros módulos.

É a exceção que o princípio XIII reserva à composition root (ADR-012). As etapas vêm de `lifecycle.py` e a ordem é a
da spec: configuração → adapters → packs → motor → API. Registry MCP (007) e validação de Assistants (003) entram nas
fases deles, acrescentando uma etapa à lista (research R1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from ai_core.bootstrap.grants import ConfiguredGrants, load_assistants, validate_flows
from ai_core.bootstrap.lifecycle import BootContext, BootReport, Stage, run_stages, shutdown
from ai_core.bootstrap.ports import ConfigSource
from ai_core.bootstrap.profiles import Profile, profile_for
from ai_core.bootstrap.settings import EnvConfigSource, Settings
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.service import ExecutionService
from ai_core.http.adapters.app import create_app
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
    return Platform(
        settings=parts.get("settings", Settings()),
        profile=parts.get("profile"),
        report=report,
        packs=parts.get("packs"),
        trace=parts.get("trace"),
        engine=parts.get("engine"),
        app=parts.get("app"),
        context=context,
    )


def _stages(source: ConfigSource, override: str | None) -> tuple[Stage, ...]:
    """As cinco etapas da Fase 1. A lista é dado: acrescentar uma não toca o executor."""
    return (
        Stage(name=STAGE_CONFIGURATION, run=lambda ctx: _configuration(ctx, source, override), critical=True),
        Stage(name=STAGE_ADAPTERS, run=_adapters, critical=True),
        Stage(name=STAGE_PACKS, run=_packs, critical=False),
        Stage(name=STAGE_ENGINE, run=_engine, critical=True),
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
    ctx.parts["assistants"] = load_assistants(settings.assistants_file)


def _adapters(ctx: BootContext) -> None:
    settings: Settings = ctx.parts["settings"]
    profile = profile_for(settings.profile)
    ctx.parts["profile"] = profile
    for port in ("clock", "trace_backend", "providers", "pack_source", "authenticator", "request_ids"):
        key = "trace" if port == "trace_backend" else port
        ctx.parts[port] = profile.build(key, settings)


def _packs(ctx: BootContext) -> None:
    settings: Settings = ctx.parts["settings"]
    config = (
        YamlPackConfigSource(settings.packs_file)
        if settings.packs_file is not None
        else InMemoryPackConfigSource({})
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
    validate_flows(ctx.parts["assistants"], engine.flows())


def _reader_of(backend: Any) -> Any:
    """Um backend que só escreve não oferece leitura; a consulta responde explicitamente (009 research R5)."""
    return backend if hasattr(backend, "read") else None


def _api(ctx: BootContext) -> None:
    ctx.parts["app"] = create_app(
        engine=ctx.parts["engine"],
        authenticator=ctx.parts["authenticator"],
        grants=ConfiguredGrants(ctx.parts["assistants"], ctx.parts["packs"]),
        request_ids=ctx.parts["request_ids"],
        clock=ctx.parts["clock"],
    )
