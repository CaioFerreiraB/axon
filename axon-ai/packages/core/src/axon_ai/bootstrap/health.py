"""Saúde agregada da plataforma (specs/011-core-bootstrap/contracts/health.md; research R16).

Implementa a porta `HealthProvider` da 008, consumida por `GET /private/v1/health` e por `axon health`. Cada item é
crítico ou não: só o armazenamento persistente e uma etapa crítica do boot tiram a instância do ar (`down`); pack em
erro, Assistant indisponível e modelo fora do ar a deixam `degraded`, e ela continua atendendo o resto (FR-012).

Cada checagem tem prazo próprio e todas rodam juntas — um provider que pendura não pendura a saúde —, e o resultado
fica em cache: o monitor consulta com frequência, e cada consulta tocaria o provider local.

Fase 3 (clarificação 1 de 2026-10-02, research R28): um item **não crítico** por servidor MCP global. É o único lugar
em que a plataforma pergunta se um servidor MCP está no ar — o boot nunca sai para a rede.

Fase 9 (R41): item **crítico** `identity` com o provedor de identidade ligado; itens não críticos `trace:usage` e
`trace:langfuse` dos destinos do trace (009); e os modelos passam a ser os **efetivos** — com as sobreposições da 003 —,
consultados a cada checagem, e não a tupla do boot.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Final, Protocol, TextIO

from axon_ai.assistants.api import ValidationReport
from axon_ai.assistants.domain.definitions import AssistantsConfig
from axon_ai.bootstrap.lifecycle import BootReport, StageStatus
from axon_ai.http.ports import HealthItem, HealthReport
from axon_ai.llm.api import ModelPolicy, ModelRef, ModelRouting
from axon_ai.mcp.api import McpServer, ServerHealth
from axon_ai.observability.api import DestinationHealth
from axon_ai.packs.api import PackRegistry, PackStatus

CHECK_TIMEOUT: Final = 3.0
"""Segundos por checagem: passou disso, o item é não saudável."""

CACHE_SECONDS: Final = 15.0
"""Validade do resultado: consultas dentro da janela não repetem as checagens."""

EXIT_CODES: Final = {"ok": 0, "degraded": 1, "down": 2}
"""Códigos de `axon health` (contracts/cli.md): um monitor de linha de comando distingue os três."""

DatabaseProbe = Callable[[], Awaitable[None]]
"""Confere o banco; levanta com o motivo — sem a URL — se não responde."""

DeclaredModels = Callable[[], Awaitable[Sequence[ModelRef]]]
"""Os modelos efetivos dos Assistants de sistema (`SystemAssistantAdmin.declared_models` da 003)."""

DestinationProbe = Callable[[], Sequence[DestinationHealth]]
"""A saúde dos destinos do trace (`TraceDestinations.health` da 009): sem I/O."""


class Validator(Protocol):
    async def validate(self) -> ValidationReport: ...


class McpServers(Protocol):
    """O que a saúde usa do registry da 007 (`McpRegistry`): os globais e a checagem de um servidor."""

    async def globals(self) -> Sequence[McpServer]: ...

    async def check(self, alias: str, *, owner: str | None = None) -> ServerHealth: ...


class PlatformHealth:
    """Os itens: `database`, `boot:<etapa>`, `identity`, `pack:<nome>`, `assistant:<nome>`, `model:<provider/modelo>`,
    `mcp:<alias>` (um por servidor MCP global; `mcp` quando listar falha) e `trace:<destino>`.

    `report` chega depois de construído: o boot termina de montar o relatório depois de criar a app.
    """

    def __init__(
        self,
        *,
        database: DatabaseProbe | None,
        packs: PackRegistry,
        assistants: Validator,
        routing: ModelRouting,
        models: Sequence[ModelRef] | DeclaredModels,
        timeout: float = CHECK_TIMEOUT,
        ttl: float = CACHE_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        mcp: McpServers | None = None,
        identity: Callable[[], str | None] | None = None,
        destinations: DestinationProbe | None = None,
    ) -> None:
        self.report: BootReport | None = None
        self._mcp = mcp
        self._identity = identity
        self._database = database
        self._packs = packs
        self._assistants = assistants
        self._routing = routing
        self._models = models
        self._destinations = destinations
        self._timeout = timeout
        self._ttl = ttl
        self._monotonic = monotonic
        self._cached: tuple[float, HealthReport] | None = None

    async def health(self) -> HealthReport:
        if self.report is None:
            return HealthReport(items=(HealthItem(name="boot", ok=False, critical=True, detail="boot em andamento"),))
        now = self._monotonic()
        if self._cached is not None and now - self._cached[0] < self._ttl:
            return self._cached[1]
        database, assistants, models, mcp = await asyncio.gather(
            self._database_items(), self._assistant_items(), self._model_items(), self._mcp_items()
        )
        report = HealthReport(
            items=(
                *database,
                *boot_items(self.report),
                *self._identity_items(),
                *self._pack_items(),
                *assistants,
                *models,
                *mcp,
                *self._destination_items(),
            )
        )
        self._cached = (now, report)
        return report

    # --- itens ------------------------------------------------------------------------------------------------------

    async def _database_items(self) -> tuple[HealthItem, ...]:
        if self._database is None:
            return ()
        _, failure = await self._attempt(self._database())
        return (HealthItem(name="database", ok=failure is None, critical=True, detail=failure),)

    def _identity_items(self) -> tuple[HealthItem, ...]:
        """Crítico com a identidade ligada (Fase 9, R41): sem chave de assinatura carregada, ninguém entra."""
        if self._identity is None:
            return ()
        failure = self._identity()
        return (HealthItem(name="identity", ok=failure is None, critical=True, detail=failure),)

    def _pack_items(self) -> tuple[HealthItem, ...]:
        return tuple(
            HealthItem(name=f"pack:{entry.name}", ok=entry.status is not PackStatus.ERROR, detail=entry.error)
            for entry in self._packs.entries()
        )

    async def _assistant_items(self) -> tuple[HealthItem, ...]:
        """Só os de sistema: a saúde responde a qualquer chave, e nomes de Assistants de usuário são privados."""
        report, failure = await self._attempt(self._assistants.validate())
        if report is None:
            return (HealthItem(name="assistants", ok=False, detail=failure),)
        return tuple(
            HealthItem(name=f"assistant:{status.name}", ok=status.available, detail="; ".join(status.reasons) or None)
            for status in report.statuses
            if status.origin == "system"
        )

    async def _model_items(self) -> tuple[HealthItem, ...]:
        if callable(self._models):
            refs, failure = await self._attempt(self._models())
            if refs is None:
                return (HealthItem(name="models", ok=False, detail=failure),)
        else:
            refs = self._models
        return tuple(await asyncio.gather(*(self._model_item(ref) for ref in refs)))

    async def _model_item(self, ref: ModelRef) -> HealthItem:
        name = f"model:{ref}"
        results, failure = await self._attempt(self._routing.check(ModelPolicy(roles={"generation": ref})))
        if not results:
            return HealthItem(name=name, ok=False, detail=failure or "sem resultado")
        return HealthItem(name=name, ok=results[0].available, detail=results[0].detail)

    async def _mcp_items(self) -> tuple[HealthItem, ...]:
        """Só os globais: os de usuário são do usuário, e a saúde responde a qualquer chave. Nunca críticos — um
        servidor fora do ar degrada, não derruba (clarificação 1)."""
        if self._mcp is None:
            return ()
        servers, failure = await self._attempt(self._mcp.globals())
        if servers is None:
            return (HealthItem(name="mcp", ok=False, detail=failure),)
        aliases = tuple(dict.fromkeys(server.alias for server in servers))
        return tuple(await asyncio.gather(*(self._mcp_item(alias) for alias in aliases)))

    async def _mcp_item(self, alias: str) -> HealthItem:
        name = f"mcp:{alias}"
        result, failure = await self._attempt(self._mcp.check(alias)) if self._mcp else (None, None)
        if result is None:
            return HealthItem(name=name, ok=False, detail=failure or "sem resultado")
        detail = result.detail
        if result.missing:
            missing = f"tools da allowlist não anunciadas: {', '.join(result.missing)}"
            detail = f"{detail}; {missing}" if detail else missing
        return HealthItem(name=name, ok=result.ok and not result.missing, detail=detail)

    def _destination_items(self) -> tuple[HealthItem, ...]:
        """Nunca críticos (R41): o Langfuse fora do ar ou o uso sem gravar degradam, não derrubam (ADR-034)."""
        if self._destinations is None:
            return ()
        return tuple(
            HealthItem(name=f"trace:{item.name}", ok=item.state != "degraded", detail=_destination_detail(item))
            for item in self._destinations()
        )

    async def _attempt[T](self, check: Awaitable[T]) -> tuple[T | None, str | None]:
        """O resultado, ou o motivo da falha — inclusive passar do prazo. Uma checagem nunca derruba a saúde."""
        try:
            return await asyncio.wait_for(check, self._timeout), None
        except TimeoutError:
            return None, f"sem resposta em {self._timeout:g} s"
        except Exception as error:
            return None, str(error) or type(error).__name__


def _destination_detail(item: DestinationHealth) -> str | None:
    if item.last_error:
        return item.last_error
    if item.dropped_24h:
        return f"{item.dropped_24h} registro(s) descartado(s) nas últimas 24 h"
    return "desligado" if item.state == "off" else None


def boot_items(report: BootReport) -> tuple[HealthItem, ...]:
    """Uma etapa do boot por item. Etapa que falhou só existe se era crítica — é o único item de boot crítico."""
    return tuple(
        HealthItem(
            name=f"boot:{outcome.name}",
            ok=outcome.status is StageStatus.OK,
            critical=outcome.status is StageStatus.FAILED,
            detail=outcome.detail,
        )
        for outcome in report.stages
    )


def declared_models(config: AssistantsConfig) -> tuple[ModelRef, ...]:
    """Os modelos declarados pelos Assistants de sistema, sem repetição — a allowlist tem padrões, não modelos."""
    refs = {str(ref): ref for definition in config.assistants.values() for ref in definition.roles.values()}
    return tuple(refs[key] for key in sorted(refs))


def health_command(report: HealthReport, out: TextIO) -> int:
    """`axon health`: um item por linha, o resultado na última, e o código do resultado."""
    width = max((len(item.name) for item in report.items), default=0)
    for item in report.items:
        line = f"{item.name.ljust(width)}  {'ok' if item.ok else 'falha'}"
        if item.critical and not item.ok:
            line += "  (crítico)"
        if item.detail:
            line += f"  — {item.detail}"
        print(line, file=out)
    print(f"status: {report.status}", file=out)
    return EXIT_CODES[report.status]
