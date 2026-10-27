"""Montagem da plataforma: **o único lugar do projeto** que instancia serviços e adapters de outros módulos.

É a exceção que o princípio XIII reserva à composition root (ADR-012). As etapas vêm de `lifecycle.py` e a ordem é a
da spec: configuração → adapters → packs → registry MCP (007) → motor → validação de Assistants (003) → API. O registry
entrou na Fase 3 como uma etapa a mais na lista, sem mudar o executor (research R1, R23).

O perfil escolhe os adapters de cada porta (R12); este arquivo não sabe qual perfil está montando. Quando há banco
(`database`), o pool pertence ao laço de eventos em que abre (R13): o de serviço abre no ciclo de vida da app, no laço
do servidor, e o boot e a linha de comando usam uma **sessão de armazenamento** própria — um pool temporário e as
portas de armazenamento reconstruídas sobre ele, pelas mesmas fábricas do perfil.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final
from zoneinfo import ZoneInfo

import psycopg
from fastapi import FastAPI
from psycopg.conninfo import conninfo_to_dict

from axon_ai.assistants.adapters import postgres_schema as assistants_schema
from axon_ai.assistants.adapters.assistants_yaml import YamlAssistantConfigSource
from axon_ai.assistants.adapters.catalogs import PackCollectionCatalog
from axon_ai.assistants.adapters.memory import InMemoryAssistantConfigSource
from axon_ai.assistants.adapters.rate_memory import InMemoryRateCounterStore
from axon_ai.assistants.adapters.tokens import SecretsTokenGenerator
from axon_ai.assistants.api import ValidationReport
from axon_ai.assistants.domain.access import OidcAudiences, OidcClaims
from axon_ai.assistants.ports import AssistantConfigSource
from axon_ai.assistants.service import AccessService, AssistantsService
from axon_ai.bootstrap import identity as identity_parts
from axon_ai.bootstrap import observability as observability_parts
from axon_ai.bootstrap.health import DatabaseProbe, PlatformHealth
from axon_ai.bootstrap.lifecycle import BootContext, BootReport, Stage, run_stages, shutdown
from axon_ai.bootstrap.ports import ConfigSource
from axon_ai.bootstrap.profiles import DEFAULT_PUBLIC_AUDIENCE, STORAGE_PORTS, Profile, profile_for
from axon_ai.bootstrap.settings import DEFAULT_DISPLAY_NAME, EnvConfigSource, Settings
from axon_ai.capabilities.adapters import postgres_schema as capabilities_schema
from axon_ai.capabilities.api import GatewayLimits
from axon_ai.capabilities.service import CapabilityService
from axon_ai.graph.adapters.langgraph import langgraph_runtime
from axon_ai.graph.api import RagSettings
from axon_ai.graph.service import ExecutionService
from axon_ai.http.adapters import postgres_schema as http_schema
from axon_ai.http.adapters.app import AdmissionLimits, create_app
from axon_ai.http.domain.images import ImageLimits
from axon_ai.http.ports import AdminSeams, InstanceBranding
from axon_ai.http.service import ConversationService
from axon_ai.identity.adapters import postgres_schema as identity_schema
from axon_ai.identity.adapters.http import router as identity_router
from axon_ai.identity.service import IdentityService
from axon_ai.llm.service import ModelRoutingService
from axon_ai.mcp.adapters import postgres_schema as mcp_schema
from axon_ai.mcp.adapters.config_yaml import YamlMcpConfigSource
from axon_ai.mcp.ports import McpConfig
from axon_ai.mcp.service import McpService
from axon_ai.observability.adapters import postgres_schema as observability_schema
from axon_ai.observability.ports import Origin
from axon_ai.observability.service import DestinationService, TraceService, UsageService
from axon_ai.packs.adapters.config_yaml import YamlPackConfigSource
from axon_ai.packs.adapters.data_dirs import LocalPackDataDirs
from axon_ai.packs.adapters.memory import InMemoryPackConfigSource
from axon_ai.packs.api import PackStatus
from axon_ai.packs.service import PackRuntime

STAGE_CONFIGURATION = "configuration"
STAGE_ADAPTERS = "adapters"
STAGE_IDENTITY = "identity"
STAGE_PACKS = "packs"
STAGE_MCP = "mcp_registry"
STAGE_ENGINE = "engine"
STAGE_ASSISTANTS = "assistants"
STAGE_API = "api"

CONNECT_TIMEOUT: Final = 10.0
"""Segundos para conectar ao banco: no boot, na linha de comando e na abertura do pool de serviço."""

logger: Final = logging.getLogger("axon_ai.bootstrap")


@dataclass(frozen=True, slots=True, kw_only=True)
class Platform:
    """O que o boot entrega. Campos ficam vazios quando a etapa que os produz não chegou a rodar."""

    settings: Settings
    profile: Profile | None
    report: BootReport
    packs: PackRuntime | None = None
    trace: TraceService | None = None
    routing: ModelRoutingService | None = None
    engine: ExecutionService | None = None
    assistants: AssistantsService | None = None
    access: AccessService | None = None
    mcp: McpService | None = None
    """O registry MCP da plataforma (007) — é por aqui que a 008 liga as rotas de MCP."""
    capabilities: CapabilityService | None = None
    conversations: ConversationService | None = None
    identity: IdentityService | None = None
    """O provedor de identidade (012), só com `AXON_IDENTITY_ENABLED`."""
    usage: UsageService | None = None
    """Uso e preços (009 US5) — os seams `UsageReportSeam` e `PriceBook` da superfície de administração."""
    destinations: DestinationService | None = None
    """Ajustes e saúde dos destinos do trace (009 US6, US7)."""
    app: FastAPI | None = None
    context: BootContext

    @property
    def ok(self) -> bool:
        return self.report.ok

    @property
    def parts(self) -> Mapping[str, Any]:
        """Tudo o que o boot construiu, por nome — é o que a linha de comando usa para abrir a própria sessão."""
        return self.context.parts

    def aclose(self) -> None:
        """Libera os recursos na ordem inversa do boot (FR-013); os destinos do trace esvaziam a fila antes (R40)."""
        shutdown(self.context)


def platform(
    *,
    profile: str | None = None,
    config: ConfigSource | None = None,
    until: str | None = None,
    overrides: Mapping[str, Any] | None = None,
    origin: Origin = observability_parts.PRODUCTION,
) -> Platform:
    """Monta a plataforma inteira. `profile` sobrepõe o da configuração — é o atalho das suítes.

    `until` para depois da etapa nomeada: é o que a linha de comando usa quando não precisa da plataforma toda — `keys`
    só precisa de configuração e adapters. `overrides` troca o adapter de uma porta (FR-014, R31): é como uma suíte
    programa o controller (`providers`) e os servidores MCP (`mcp_transports`). Só existe nesta chamada — nenhuma
    variável de ambiente nem arquivo a expõe. `origin` marca as linhas de uso do processo: `evaluation` no `axon eval
    run`, para o harness não virar produção no relatório (009, clarificação de 2026-10-13; R40).
    """
    source = config or EnvConfigSource()
    context = BootContext()
    context.parts["overrides"] = dict(overrides or {})
    context.parts["origin"] = origin
    stages = _stages(source, profile)
    if until is not None:
        stages = stages[: [stage.name for stage in stages].index(until) + 1]
    report, context = run_stages(stages, context)
    parts = context.parts
    health = parts.get("health")
    if isinstance(health, PlatformHealth):
        health.report = report
    return Platform(
        settings=parts.get("settings", Settings()),
        profile=parts.get("profile"),
        report=report,
        packs=parts.get("packs"),
        trace=parts.get("trace"),
        routing=parts.get("routing"),
        engine=parts.get("engine"),
        assistants=parts.get("assistants"),
        access=parts.get("access"),
        mcp=parts.get("mcp"),
        capabilities=parts.get("capabilities"),
        conversations=parts.get("conversation_service"),
        identity=parts.get("identity"),
        usage=parts.get("usage"),
        destinations=parts.get("destinations"),
        app=parts.get("app"),
        context=context,
    )


def _stages(source: ConfigSource, override: str | None) -> tuple[Stage, ...]:
    """As etapas registradas. A lista é dado: acrescentar uma não toca o executor."""
    return (
        Stage(name=STAGE_CONFIGURATION, run=lambda ctx: _configuration(ctx, source, override), critical=True),
        Stage(name=STAGE_ADAPTERS, run=_adapters, critical=True),
        Stage(name=STAGE_IDENTITY, run=_identity, critical=True),
        Stage(name=STAGE_PACKS, run=_packs, critical=False),
        Stage(name=STAGE_MCP, run=_mcp_registry, critical=True),
        Stage(name=STAGE_ENGINE, run=_engine, critical=True),
        Stage(name=STAGE_ASSISTANTS, run=_assistants, critical=False),
        Stage(name=STAGE_API, run=_api, critical=True),
    )


def _configuration(ctx: BootContext, source: ConfigSource, override: str | None) -> None:
    settings = source.load()
    if override is not None and override != settings.profile:
        settings = dataclasses.replace(settings, profile=override)
    ctx.parts["settings"] = settings
    # Erro de arquivo no assistants.yaml para o boot aqui; erro de um Assistant só o deixa indisponível (003 FR-011).
    ctx.parts["assistants_config"] = assistants_source(settings).load()
    # O mcp.yaml também: o transporte HTTP precisa dos hosts dele já na etapa de adapters (R23). Arquivo ilegível ou
    # malformado para o boot aqui; uma entrada com problema só deixa aquele servidor indisponível.
    ctx.parts["mcp_config"] = mcp_config(settings)


def mcp_config(settings: Settings) -> McpConfig:
    """O arquivo de servidores MCP do operador (formato da 007), ou nenhum servidor."""
    if settings.mcp_file is None:
        return McpConfig()
    return YamlMcpConfigSource(settings.mcp_file).load()


def assistants_source(settings: Settings) -> AssistantConfigSource:
    """O `assistants.yaml` configurado, ou nenhum Assistant."""
    if settings.assistants_file is None:
        return InMemoryAssistantConfigSource({})
    return YamlAssistantConfigSource(settings.assistants_file)


def _adapters(ctx: BootContext) -> None:
    """Instancia o adapter de cada porta, na ordem da lista do perfil. Com banco, confere a conexão e migra os schemas
    `assistants` e `http` numa sessão própria — falha aqui para o boot antes de a API existir (SC-002, R13)."""
    settings: Settings = ctx.parts["settings"]
    profile = profile_for(settings.profile)
    ctx.parts["profile"] = profile
    built = profile.build_all(settings, ctx.parts, overrides=ctx.parts.get("overrides"))
    ctx.parts["trace_backend"] = built.pop("trace")
    ctx.parts.update(built)
    if ctx.parts["database"] is not None:
        _run(_migrate(ctx.parts))


async def _migrate(parts: Mapping[str, Any]) -> None:
    async with storage(parts) as session:
        now = parts["clock"].now()
        async with _database_errors(parts["settings"]):
            await assistants_schema.migrate(session["database"], now=now)
            await http_schema.migrate(session["database"], now=now)
            await mcp_schema.migrate(session["database"], now=now)
            await capabilities_schema.migrate(session["database"], now=now)
            await identity_schema.migrate(session["database"], now=now)
            await observability_schema.migrate(session["database"], now=now)


def _identity(ctx: BootContext) -> None:
    """A 012, só com a identidade ligada (R37): chave de assinatura e admin inicial antes de a API existir, e o
    verificador da 003 passa a ler as chaves em processo. Crítica: sem ela, ninguém entra."""
    parts = ctx.parts
    settings: Settings = parts["settings"]
    if not settings.identity_enabled:
        return
    identity_parts.prepare(parts)
    service = identity_parts.identity_service(parts, session=parts)
    _run(_start_identity(parts, service))
    parts["identity"] = service
    if "oidc" not in parts.get("overrides", {}):
        parts["oidc"] = identity_parts.verifier(service)


async def _start_identity(parts: Mapping[str, Any], service: IdentityService) -> None:
    """Sem banco, o próprio serviço da plataforma; com banco, um serviço sobre a sessão do boot — o de runtime carrega
    as chaves quando o pool de serviço abre (`app_lifespan`)."""
    if parts["database"] is None:
        await service.start()
        await service.bootstrap_admin()
        return
    async with storage(parts) as session, _database_errors(parts["settings"]):
        boot = identity_parts.identity_service(parts, session=session)
        await boot.start()
        await boot.bootstrap_admin()


def _packs(ctx: BootContext) -> None:
    runtime = pack_runtime(ctx.parts)
    runtime.load()
    ctx.parts["packs"] = runtime

    broken = [entry for entry in runtime.entries() if entry.status is PackStatus.ERROR]
    if broken:
        # Pack em erro degrada a etapa e o boot segue: os demais packs atendem (princípio VII, SC-004).
        ctx.parts[f"{STAGE_PACKS}:degraded"] = "; ".join(f"pack '{e.name}': {e.error}" for e in broken)


def pack_runtime(parts: Mapping[str, Any]) -> PackRuntime:
    """O Pack Registry, ainda não carregado: `packs list` e `packs check` o carregam para distinguir `packs.yaml`
    malformado (código 2) de pack em erro, e `packs prepare` não o carrega. Os diretórios de dados vêm da mesma raiz
    nos três perfis: são do operador, não um armazenamento que o perfil troca (ADR-041, R54)."""
    settings: Settings = parts["settings"]
    config = (
        YamlPackConfigSource(settings.packs_file) if settings.packs_file is not None else InMemoryPackConfigSource({})
    )
    return PackRuntime(parts["pack_source"], config, LocalPackDataDirs(settings.packs_data_dir))


MCP_LOGGER: Final = "mcp"
"""Raiz dos loggers do SDK de MCP. Em `DEBUG`, o SDK registra mensagens JSON-RPC inteiras — argumentos e conteúdo de
tool —; os filhos não têm nível próprio e herdam o que for fixado aqui (R30)."""


def _mcp_registry(ctx: BootContext) -> None:
    """Monta o registry MCP da 007 com as portas do perfil. Não sai para a rede (clarificação 1 de 2026-10-02).

    Entrada do arquivo com problema, ou referência de credencial que o ambiente não resolve, degrada a etapa nomeando
    o alias — e nunca um valor (FR-009) —; o resto sobe (FR-003).
    """
    logging.getLogger(MCP_LOGGER).setLevel(logging.INFO)
    parts = ctx.parts
    parts["mcp"] = mcp_service(parts, store=parts["mcp_store"])
    config: McpConfig = parts["mcp_config"]
    problems = [f"mcp '{entry.alias}': {entry.problem}" for entry in config.entries if entry.problem is not None]
    problems.extend(_run(_missing_credentials(parts)))
    if problems:
        ctx.parts[f"{STAGE_MCP}:degraded"] = "; ".join(problems)


async def _missing_credentials(parts: Mapping[str, Any]) -> list[str]:
    """Referências dos servidores globais (arquivo e armazenamento) que o ambiente não resolve — sem ler valor algum."""
    secrets = parts["mcp_secrets"]
    config: McpConfig = parts["mcp_config"]
    refs: list[tuple[str, str]] = [
        (entry.alias, ref)
        for entry in config.entries
        if entry.stdio is not None
        for ref in entry.stdio.secrets.values()
    ]
    async with storage(parts) as session:
        servers = await mcp_service(parts, store=session["mcp_store"]).globals()
    refs.extend((server.alias, server.credential_ref) for server in servers if server.credential_ref is not None)
    return [
        f"mcp '{alias}': credencial '{ref}' ausente (AXON_MCP_SECRET_{ref.upper()})"
        for alias, ref in dict.fromkeys(refs)
        if secrets.resolve(ref) is None
    ]


def mcp_service(parts: Mapping[str, Any], *, store: Any) -> McpService:
    """O registry da 007 sobre o armazenamento dado: o da plataforma no servidor, o de uma sessão no boot e na linha de
    comando (R13, R25). Arquivo, transportes, segredos, cache e relógio são os mesmos."""
    settings: Settings = parts["settings"]
    return McpService(
        store=store,
        config=parts["mcp_config"],
        transports=parts["mcp_transports"],
        secrets=parts["mcp_secrets"],
        cache=parts["mcp_cache"],
        clock=parts["clock"],
        discovery_ttl=timedelta(seconds=settings.mcp_discovery_ttl),
        max_attachment_bytes=settings.tool_max_attachment_bytes,
    )


def capabilities_service(parts: Mapping[str, Any], *, audit: Any, mcp: McpService) -> CapabilityService:
    """O gateway de tools da 004: tools dos packs pelo seam Pack Toolset (002), MCP pelo registry, auditoria dada."""
    settings: Settings = parts["settings"]
    return CapabilityService(
        pack_tools=parts["packs"],
        mcp=mcp,
        audit=audit,
        trace=parts["trace"],
        clock=parts["clock"],
        limits=GatewayLimits(timeout_ms=settings.tool_timeout_ms, max_response_bytes=settings.tool_max_response_bytes),
    )


def _engine(ctx: BootContext) -> None:
    clock = ctx.parts["clock"]
    backend = ctx.parts["trace_backend"]
    # Os destinos da 009 (R40): o primário síncrono e, fora do caminho de quem emite, o uso e o Langfuse; a captura de
    # conteúdo é lida dos ajustes efetivos a cada evento.
    observability = observability_parts.trace_parts(ctx.parts)
    trace = TraceService(
        exporter=backend,
        reader=_reader_of(backend),
        clock=clock,
        destinations=(observability.usage_destination, observability.langfuse_destination),
        capture=observability.destinations.capture_enabled,
    )
    ctx.parts["trace"] = trace
    ctx.parts["usage_destination"] = observability.usage_destination
    ctx.parts["destinations"] = observability.destinations
    ctx.parts["usage"] = observability.usage
    ctx.closers.append(lambda: _close_trace(trace, ctx.parts["langfuse_transport"]))
    if ctx.parts["database"] is None:
        # Com banco, os ajustes gravados são lidos quando o pool de serviço abre (`app_lifespan`, R13).
        _run(observability.destinations.start())

    routing = ModelRoutingService(providers=ctx.parts["providers"], trace=trace, clock=clock)
    ctx.parts["routing"] = routing
    capabilities = capabilities_service(ctx.parts, audit=ctx.parts["audit"], mcp=ctx.parts["mcp"])
    ctx.parts["capabilities"] = capabilities
    # Com o gateway, o motor oferece `agentic` (ADR-018, R24) e `rag_first` (005 Fase 5).
    ctx.parts["engine"] = ExecutionService(
        flows=langgraph_runtime(),
        hooks=ctx.parts["packs"],
        routing=routing,
        trace=trace,
        clock=clock,
        capabilities=capabilities,
        rag=_rag(ctx.parts["settings"]),
        timezone=ZoneInfo(ctx.parts["settings"].timezone),
    )


def _close_trace(trace: TraceService, transport: Any) -> None:
    """Esvazia os destinos e desliga o exportador do Langfuse: o que estava na fila sai antes de o processo terminar."""
    with suppress(Exception):
        _run(trace.flush())
    transport.shutdown()


def _rag(settings: Settings) -> RagSettings:
    """Os números do `rag_first` do operador (`AXON_RAG_*`, já validados em `Settings`; 005 research R44)."""
    return RagSettings(
        candidates=settings.rag_candidates, passages=settings.rag_passages, min_score=settings.rag_min_score
    )


def _reader_of(backend: Any) -> Any:
    """Um backend que só escreve não oferece leitura; a consulta responde explicitamente (009 research R5)."""
    return backend if hasattr(backend, "read") else None


def _assistants(ctx: BootContext) -> None:
    """Monta os serviços da 003 e valida todos os Assistants contra packs, flows, MCPs e coleções (003 FR-011).

    Assistant indisponível degrada a etapa com o motivo e o resto serve — como pack em erro (011 FR-003).
    """
    parts = ctx.parts
    ctx.parts["assistants"] = assistants_service(
        parts, users=parts["user_assistants"], mcp=parts["mcp"], overrides=parts["system_overrides"]
    )
    ctx.parts["access"] = access_service(parts, keys=parts["api_keys"])
    report = _run(_validate(parts))
    unavailable = [status for status in report.statuses if not status.available]
    if unavailable:
        ctx.parts[f"{STAGE_ASSISTANTS}:degraded"] = "; ".join(
            f"assistant '{status.name}': {'; '.join(status.reasons)}" for status in unavailable
        )


async def _validate(parts: Mapping[str, Any]) -> ValidationReport:
    async with storage(parts) as session:
        return await session_assistants(parts, session).validate()


def session_assistants(parts: Mapping[str, Any], session: Mapping[str, Any]) -> AssistantsService:
    """Os serviços da 003 sobre o armazenamento de uma sessão: Assistants de usuário, sobreposições e registry MCP dela
    (R13, R25)."""
    return assistants_service(
        parts,
        users=session["user_assistants"],
        mcp=mcp_service(parts, store=session["mcp_store"]),
        overrides=session["system_overrides"],
    )


def assistants_service(parts: Mapping[str, Any], *, users: Any, mcp: Any, overrides: Any) -> AssistantsService:
    """Resolução de grant, diretório, validação e sobreposições (003), sobre os armazenamentos de Assistants de usuário
    e de sobreposições e o diretório de MCP dados. O diretório é o registry da 007 (R25)."""
    return AssistantsService(
        config=parts["assistants_config"],
        packs=parts["packs"],
        flows=parts["engine"].flows(),
        flow_roles=parts["engine"].flow_roles(),
        users=users,
        mcp=mcp,
        collections=PackCollectionCatalog(parts["packs"]),
        rate=InMemoryRateCounterStore(),
        clock=parts["clock"],
        overrides=overrides,
    )


def access_service(parts: Mapping[str, Any], *, keys: Any) -> AccessService:
    """Autenticação real e administração de chaves (003, FR-015), sobre o armazenamento de chaves dado."""
    settings: Settings = parts["settings"]
    return AccessService(
        keys=keys,
        oidc=parts["oidc"],
        tokens=SecretsTokenGenerator(),
        clock=parts["clock"],
        claims=_oidc_claims(settings),
        admin_group=parts["assistants_config"].admin_group,
        audiences=OidcAudiences(public=settings.oidc_audience or DEFAULT_PUBLIC_AUDIENCE),
    )


def _oidc_claims(settings: Settings) -> OidcClaims:
    """Com a identidade da plataforma, o subject é o nome de usuário (`preferred_username`), como na Fase 7 — ACL e
    donos já gravados continuam valendo (012 R10, 003 design); com um emissor externo, o que a configuração disser."""
    if settings.identity_enabled:
        return OidcClaims(subject_claim="preferred_username", groups_claim="groups")
    return OidcClaims(subject_claim=settings.oidc_subject_claim, groups_claim=settings.oidc_groups_claim)


def _api(ctx: BootContext) -> None:
    parts = ctx.parts
    settings: Settings = parts["settings"]
    retention = timedelta(days=settings.conversation_retention_days)
    conversations = ConversationService(store=parts["conversations"], clock=parts["clock"], retention=retention)
    ctx.parts["conversation_service"] = conversations
    health = platform_health(parts, session=parts)
    ctx.parts["health"] = health
    expiry = PeriodicTask(
        name="conversations.expire", interval=settings.conversation_expiry_interval, run=conversations.expire
    )
    usage: UsageService = parts["usage"]
    destinations: DestinationService = parts["destinations"]
    trace: TraceService = parts["trace"]
    tasks = [
        expiry,
        PeriodicTask(
            name="usage.flush", interval=observability_parts.USAGE_FLUSH_INTERVAL, run=parts["usage_destination"].flush
        ),
        PeriodicTask(
            name="usage.purge",
            interval=observability_parts.USAGE_PURGE_INTERVAL,
            run=lambda: usage.purge(retention_days=settings.usage_retention_days),
        ),
    ]
    startups: list[Callable[[], Awaitable[object]]] = []
    if parts["database"] is not None:
        startups.append(destinations.start)
    identity: IdentityService | None = parts.get("identity")
    if identity is not None:
        tasks.append(
            PeriodicTask(name="identity.purge", interval=identity_parts.IDENTITY_PURGE_INTERVAL, run=identity.purge)
        )
        if parts["database"] is not None:
            startups.append(identity.start)
    app = create_app(
        engine=parts["engine"],
        authenticator=parts["access"],
        grants=parts["assistants"],
        directory=parts["assistants"],
        keys=parts["access"],
        packs=parts["packs"],
        admin=parts["access"],
        conversations=parts["conversations"],
        health=health,
        request_ids=parts["request_ids"],
        conversation_ids=parts["conversation_ids"],
        clock=parts["clock"],
        conversation_retention=retention,
        lifespan=app_lifespan(database=parts["database"], tasks=tasks, startups=startups, shutdowns=[trace.flush]),
        admission=AdmissionLimits(
            max_executions=settings.max_executions,
            queue_size=settings.queue_size,
            max_wait=timedelta(milliseconds=settings.queue_wait_ms),
        ),
        mcp=parts["mcp"],
        admin_seams=AdminSeams(
            assistants=parts["assistants"],
            models=parts["routing"],
            usage=usage,
            prices=usage,
            destinations=destinations,
            default_timezone=settings.usage_timezone,
            accounts=identity,
            login=identity,
        ),
        instance=_instance(settings, identity),
        image_limits=ImageLimits(
            max_request_bytes=settings.max_request_bytes,
            max_input_image_bytes=settings.max_input_image_bytes,
            max_input_images=settings.max_input_images,
        ),
    )
    if identity is not None:
        # O protocolo e as páginas da 012 são o adapter primário dela, montado no mesmo app (ADR-030).
        app.include_router(identity_router(identity, identity_parts.http_settings(settings)))
    ctx.parts["app"] = app


def _instance(settings: Settings, identity: IdentityService | None) -> InstanceBranding:
    """Nome e logotipo da instalação para o `/admin/v1/me` (008 R48): o logotipo é servido pela 012."""
    logo = "/oauth2/assets/logo" if identity is not None and settings.logo_file is not None else None
    custom = settings.display_name != DEFAULT_DISPLAY_NAME or logo is not None
    return InstanceBranding(name=settings.display_name, logo_url=logo, custom=custom)


def platform_health(
    parts: Mapping[str, Any], *, session: Mapping[str, Any], identity: IdentityService | None = None
) -> PlatformHealth:
    """A saúde agregada sobre o armazenamento de `session`: o da plataforma na API, o de uma sessão própria na linha de
    comando (R13). O relatório de boot é atribuído depois, por quem o tem. `identity`: a de `session_identity` na linha
    de comando (R34); sem ela, a da plataforma."""
    database = session["database"]
    assistants = session_assistants(parts, session)
    destinations: DestinationService | None = parts.get("destinations")
    return PlatformHealth(
        database=_select_one(database, parts["settings"]) if database is not None else None,
        packs=parts["packs"],
        assistants=assistants,
        mcp=mcp_service(parts, store=session["mcp_store"]),
        routing=parts["routing"],
        # Os efetivos, com as sobreposições da 003, a cada checagem (R41).
        models=assistants.declared_models,
        identity=_identity_probe(identity if identity is not None else parts.get("identity")),
        destinations=destinations.health if destinations is not None else None,
    )


async def session_identity(parts: Mapping[str, Any], session: Mapping[str, Any]) -> IdentityService | None:
    """A identidade que a saúde da linha de comando confere (R34). Com banco, as chaves de assinatura só chegam ao
    serviço da plataforma quando o ciclo de vida da app abre o pool — que a linha de comando não abre —; então, como no
    boot (`_start_identity`), um serviço sobre a sessão do comando, iniciado como o servidor o inicia. Sem banco, a
    própria."""
    service: IdentityService | None = parts.get("identity")
    if service is None or parts.get("database") is None:
        return service
    on_session = identity_parts.identity_service(parts, session=session)
    async with _database_errors(parts["settings"]):
        await on_session.start()
    return on_session


def _identity_probe(service: IdentityService | None) -> Callable[[], str | None] | None:
    """Item crítico `identity` (R41): sem chave publicada, nenhum token verifica."""
    if service is None:
        return None

    def probe() -> str | None:
        keys = service.jwks().get("keys")
        return None if isinstance(keys, list) and keys else "nenhuma chave de assinatura carregada"

    return probe


# --- ciclo de vida da app (R14) ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class PeriodicTask:
    """Tarefa declarada por um módulo, agendada no ciclo de vida da app: hoje, a expiração de conversas (008 FR-019)."""

    name: str
    interval: float
    run: Callable[[], Awaitable[object]]


def app_lifespan(
    *,
    database: Any | None,
    tasks: Sequence[PeriodicTask],
    startups: Sequence[Callable[[], Awaitable[object]]] = (),
    shutdowns: Sequence[Callable[[], Awaitable[object]]] = (),
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """No início, abre o pool de serviço, roda o que precisa dele antes da primeira requisição (as chaves da 012, os
    ajustes dos destinos da 009) e agenda as tarefas; no fim, cancela as tarefas, roda o que ainda precisa do pool (o
    último lote de uso) e fecha o pool.

    É o único lugar com o laço do servidor em execução — e o pool pertence ao laço em que abre (R13). Um pool não
    reabre depois de fechado: a app de uma plataforma persistente serve uma vez.
    """

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await database.open(wait=True, timeout=CONNECT_TIMEOUT)
        for startup in startups:
            await startup()
        running = [asyncio.create_task(_repeat(task), name=task.name) for task in tasks]
        try:
            yield
        finally:
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)
            for step in shutdowns:
                try:
                    await step()
                except Exception:
                    logger.exception("encerramento: uma etapa falhou; as demais seguem")
            if database is not None:
                await database.close()

    return lifespan


async def _repeat(task: PeriodicTask) -> None:
    """Roda já no início — um processo que reinicia antes do intervalo não pode adiar a tarefa para sempre — e depois
    a cada intervalo. Uma execução que falha é registrada e a seguinte acontece no horário."""
    while True:
        try:
            await task.run()
        except Exception:
            logger.exception("tarefa periódica '%s' falhou; nova tentativa em %s s", task.name, task.interval)
        await asyncio.sleep(task.interval)


# --- sessão de armazenamento (R13) ------------------------------------------------------------------------------------


class DatabaseUnavailable(RuntimeError):
    """A porta `database` falhou. A mensagem nomeia a porta e o adapter — nunca a URL (FR-009)."""


@asynccontextmanager
async def storage(parts: Mapping[str, Any]) -> AsyncIterator[Mapping[str, Any]]:
    """As portas de armazenamento utilizáveis no laço corrente.

    Sem banco, são as da plataforma. Com banco, fora do laço do servidor — no boot e na linha de comando —, confere a
    conexão, abre um pool temporário e reconstrói as portas de `STORAGE_PORTS` sobre ele, pelas fábricas do perfil.
    """
    if parts.get("database") is None:
        yield parts
        return
    settings: Settings = parts["settings"]
    profile: Profile = parts["profile"]
    session = dict(parts)
    pool = profile.build("database", settings, session)
    try:
        async with _database_errors(settings):
            await _check_connection(settings)
            await pool.open(wait=True, timeout=CONNECT_TIMEOUT)
        session["database"] = pool
        for port in STORAGE_PORTS:
            session[port] = profile.build(port, settings, session)
        yield session
    finally:
        await pool.close()


async def _check_connection(settings: Settings) -> None:
    """Uma conexão direta antes do pool: a causa (recusada, senha, banco inexistente) sai na hora, e não um tempo
    esgotado do pool depois de `CONNECT_TIMEOUT` segundos tentando de novo."""
    url = settings.database_url or ""
    connection = await psycopg.AsyncConnection.connect(url, connect_timeout=int(CONNECT_TIMEOUT))
    await connection.close()


@asynccontextmanager
async def _database_errors(settings: Settings) -> AsyncIterator[None]:
    """Traduz falha de banco e de migração num erro que nomeia porta e adapter, com o texto sem a URL nem a senha."""
    try:
        yield
    except (
        psycopg.Error,
        assistants_schema.MigrationError,
        http_schema.MigrationError,
        identity_schema.MigrationError,
        observability_schema.MigrationError,
    ) as error:
        detail = _redact(str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__, settings)
        raise DatabaseUnavailable(f"porta 'database' (adapter Postgres): {detail}") from None


def _select_one(pool: Any, settings: Settings) -> DatabaseProbe:
    async def probe() -> None:
        async with _database_errors(settings), pool.connection() as connection:
            await connection.execute("SELECT 1")

    return probe


def _redact(text: str, settings: Settings) -> str:
    url = settings.database_url or ""
    secrets = [url]
    with suppress(psycopg.Error):
        secrets.append(str(conninfo_to_dict(url).get("password") or ""))
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    """Roda uma corrotina no boot, que é síncrono — inclusive quando quem chama já está dentro de um laço de eventos
    (a suíte de um pack que monta a plataforma num teste assíncrono)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()
