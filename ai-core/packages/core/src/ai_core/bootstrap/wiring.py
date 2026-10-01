"""Montagem da plataforma: **o único lugar do projeto** que instancia serviços e adapters de outros módulos.

É a exceção que o princípio XIII reserva à composition root (ADR-012). As etapas vêm de `lifecycle.py` e a ordem é a
da spec: configuração → adapters → packs → motor → validação de Assistants (003) → API. O registry MCP (007) entra na
fase dele, acrescentando uma etapa à lista (research R1).

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

import psycopg
from fastapi import FastAPI
from psycopg.conninfo import conninfo_to_dict

from ai_core.assistants.adapters import postgres_schema as assistants_schema
from ai_core.assistants.adapters.assistants_yaml import YamlAssistantConfigSource
from ai_core.assistants.adapters.catalogs import EmptyCollectionCatalog, EmptyMcpDirectory
from ai_core.assistants.adapters.memory import InMemoryAssistantConfigSource
from ai_core.assistants.adapters.rate_memory import InMemoryRateCounterStore
from ai_core.assistants.adapters.tokens import SecretsTokenGenerator
from ai_core.assistants.api import ValidationReport
from ai_core.assistants.domain.access import OidcClaims
from ai_core.assistants.ports import AssistantConfigSource
from ai_core.assistants.service import AccessService, AssistantsService
from ai_core.bootstrap.health import DatabaseProbe, PlatformHealth, declared_models
from ai_core.bootstrap.lifecycle import BootContext, BootReport, Stage, run_stages, shutdown
from ai_core.bootstrap.ports import ConfigSource
from ai_core.bootstrap.profiles import STORAGE_PORTS, Profile, profile_for
from ai_core.bootstrap.settings import EnvConfigSource, Settings
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.service import ExecutionService
from ai_core.http.adapters import postgres_schema as http_schema
from ai_core.http.adapters.app import create_app
from ai_core.http.service import ConversationService
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

CONNECT_TIMEOUT: Final = 10.0
"""Segundos para conectar ao banco: no boot, na linha de comando e na abertura do pool de serviço."""

logger: Final = logging.getLogger("ai_core.bootstrap")


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
    conversations: ConversationService | None = None
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
        """Libera os recursos na ordem inversa do boot (FR-013)."""
        shutdown(self.context)


def platform(
    *, profile: str | None = None, config: ConfigSource | None = None, until: str | None = None
) -> Platform:
    """Monta a plataforma inteira. `profile` sobrepõe o da configuração — é o atalho das suítes.

    `until` para depois da etapa nomeada: é o que a linha de comando usa quando não precisa da plataforma toda — `keys`
    só precisa de configuração e adapters.
    """
    source = config or EnvConfigSource()
    context = BootContext()
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
        conversations=parts.get("conversation_service"),
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
        settings = dataclasses.replace(settings, profile=override)
    ctx.parts["settings"] = settings
    # Erro de arquivo no assistants.yaml para o boot aqui; erro de um Assistant só o deixa indisponível (003 FR-011).
    ctx.parts["assistants_config"] = assistants_source(settings).load()


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
    built = profile.build_all(settings, ctx.parts)
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
    malformado (código 2) de pack em erro."""
    settings: Settings = parts["settings"]
    config = (
        YamlPackConfigSource(settings.packs_file) if settings.packs_file is not None else InMemoryPackConfigSource({})
    )
    return PackRuntime(parts["pack_source"], config)


def _engine(ctx: BootContext) -> None:
    clock = ctx.parts["clock"]
    backend = ctx.parts["trace_backend"]
    trace = TraceService(exporter=backend, reader=_reader_of(backend), clock=clock)
    ctx.parts["trace"] = trace

    routing = ModelRoutingService(providers=ctx.parts["providers"], trace=trace, clock=clock)
    ctx.parts["routing"] = routing
    ctx.parts["engine"] = ExecutionService(
        flows=langgraph_runtime(),
        hooks=ctx.parts["packs"],
        routing=routing,
        trace=trace,
        clock=clock,
    )


def _reader_of(backend: Any) -> Any:
    """Um backend que só escreve não oferece leitura; a consulta responde explicitamente (009 research R5)."""
    return backend if hasattr(backend, "read") else None


def _assistants(ctx: BootContext) -> None:
    """Monta os serviços da 003 e valida todos os Assistants contra packs, flows, MCPs e coleções (003 FR-011).

    Assistant indisponível degrada a etapa com o motivo e o resto serve — como pack em erro (011 FR-003).
    """
    parts = ctx.parts
    ctx.parts["assistants"] = assistants_service(parts, users=parts["user_assistants"])
    ctx.parts["access"] = access_service(parts, keys=parts["api_keys"])
    report = _run(_validate(parts))
    unavailable = [status for status in report.statuses if not status.available]
    if unavailable:
        ctx.parts[f"{STAGE_ASSISTANTS}:degraded"] = "; ".join(
            f"assistant '{status.name}': {'; '.join(status.reasons)}" for status in unavailable
        )


async def _validate(parts: Mapping[str, Any]) -> ValidationReport:
    async with storage(parts) as session:
        return await assistants_service(parts, users=session["user_assistants"]).validate()


def assistants_service(parts: Mapping[str, Any], *, users: Any) -> AssistantsService:
    """Resolução de grant, diretório e validação (003), sobre o armazenamento de Assistants de usuário dado."""
    return AssistantsService(
        config=parts["assistants_config"],
        packs=parts["packs"],
        flows=parts["engine"].flows(),
        users=users,
        mcp=EmptyMcpDirectory(),
        collections=EmptyCollectionCatalog(),
        rate=InMemoryRateCounterStore(),
        clock=parts["clock"],
    )


def access_service(parts: Mapping[str, Any], *, keys: Any) -> AccessService:
    """Autenticação real e administração de chaves (003, FR-015), sobre o armazenamento de chaves dado."""
    settings: Settings = parts["settings"]
    return AccessService(
        keys=keys,
        oidc=parts["oidc"],
        tokens=SecretsTokenGenerator(),
        clock=parts["clock"],
        claims=OidcClaims(subject_claim=settings.oidc_subject_claim, groups_claim=settings.oidc_groups_claim),
        admin_group=parts["assistants_config"].admin_group,
    )


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
    ctx.parts["app"] = create_app(
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
        lifespan=app_lifespan(database=parts["database"], tasks=(expiry,)),
    )


def platform_health(parts: Mapping[str, Any], *, session: Mapping[str, Any]) -> PlatformHealth:
    """A saúde agregada sobre o armazenamento de `session`: o da plataforma na API, o de uma sessão própria na linha de
    comando (R13). O relatório de boot é atribuído depois, por quem o tem."""
    database = session["database"]
    return PlatformHealth(
        database=_select_one(database, parts["settings"]) if database is not None else None,
        packs=parts["packs"],
        assistants=assistants_service(parts, users=session["user_assistants"]),
        routing=parts["routing"],
        models=declared_models(parts["assistants_config"]),
    )


# --- ciclo de vida da app (R14) ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class PeriodicTask:
    """Tarefa declarada por um módulo, agendada no ciclo de vida da app: hoje, a expiração de conversas (008 FR-019)."""

    name: str
    interval: float
    run: Callable[[], Awaitable[object]]


def app_lifespan(
    *, database: Any | None, tasks: Sequence[PeriodicTask]
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """No início, abre o pool de serviço e agenda as tarefas; no fim, cancela as tarefas e fecha o pool.

    É o único lugar com o laço do servidor em execução — e o pool pertence ao laço em que abre (R13). Um pool não
    reabre depois de fechado: a app de uma plataforma persistente serve uma vez.
    """

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await database.open(wait=True, timeout=CONNECT_TIMEOUT)
        running = [asyncio.create_task(_repeat(task), name=task.name) for task in tasks]
        try:
            yield
        finally:
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)
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
    except (psycopg.Error, assistants_schema.MigrationError, http_schema.MigrationError) as error:
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
