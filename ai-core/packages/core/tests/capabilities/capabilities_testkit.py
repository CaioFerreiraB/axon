"""Fábricas dos testes da 004: grants, packs falsos, cliente MCP programado, trace que grava e a sessão montada."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from ai_core.assistants.api import ExecutionGrant, Limits, Principal
from ai_core.capabilities.adapters.memory import InMemoryAuditLog, StaticPackTools
from ai_core.capabilities.api import GatewayLimits, ToolContext
from ai_core.capabilities.ports import AuditLog, PackTool
from ai_core.llm.api import ModelPolicy, ModelRef
from ai_core.mcp.api import Discovery, UnknownServer
from ai_core.observability.api import TraceEvent
from ai_core.packs.api import Composition
from axon_ai_contracts import (
    Chunk,
    JSONValue,
    NamedRetriever,
    ToolInvocation,
    ToolResult,
    ToolSpec,
    retrieval_tool_spec,
)

T0: Final = datetime(2026, 10, 1, 12, tzinfo=UTC)
REFERENCE: Final = datetime(2026, 9, 30, tzinfo=UTC)

ANA: Final = Principal(subject="user:ana", scheme="oidc")

TEXT_SCHEMA: Final[Mapping[str, JSONValue]] = {
    "type": "object",
    "properties": {"texto": {"type": "string"}},
    "required": ["texto"],
    "additionalProperties": False,
}
EMPTY_SCHEMA: Final[Mapping[str, JSONValue]] = {"type": "object", "properties": {}, "additionalProperties": False}


# --- relógio, trace, contexto -----------------------------------------------------------------------------------------


class FakeClock:
    """`now` fixo e ajustável; `monotonic` devolve as leituras programadas, repetindo a última."""

    def __init__(self, at: datetime = T0, readings: Sequence[float] = (0.0, 0.25)) -> None:
        self.at = at
        self._readings = list(readings)

    def now(self) -> datetime:
        return self.at

    def monotonic(self) -> float:
        return self._readings.pop(0) if len(self._readings) > 1 else self._readings[0]


class RecordingTraceSink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)

    def of_type(self, kind: type) -> list[Any]:
        return [event for event in self.events if isinstance(event, kind)]


def context(**overrides: Any) -> ToolContext:
    base: dict[str, Any] = {"request_id": "req-1", "reference_time": REFERENCE}
    return ToolContext(**(base | overrides))


def grant(
    *,
    packs: Sequence[str] = (),
    mcp: Sequence[str] = (),
    collections: Sequence[str] = (),
    allowed: Sequence[str] | None = None,
    write: Sequence[str] = (),
    assistant: str = "geral",
    principal: Principal = ANA,
) -> ExecutionGrant:
    return ExecutionGrant(
        assistant=assistant,
        principal=principal,
        flow="agentic",
        composition=Composition(packs=tuple(packs)),
        mcp_aliases=frozenset(mcp),
        collections=frozenset(collections),
        allowed_tools=frozenset(allowed) if allowed is not None else None,
        write_tools=frozenset(write),
        models=ModelPolicy(roles={"generation": ModelRef(provider="ollama", model="m")}, allow=("ollama/*",)),
        limits=Limits(),
    )


# --- tools de pack ----------------------------------------------------------------------------------------------------


@dataclass(slots=True)
class Calls:
    """O que handlers, retrievers e o cliente MCP receberam — para conferir o que executou e o que não."""

    native: list[tuple[str, ToolInvocation]] = field(default_factory=list)
    retrieval: list[tuple[str, str, int | None, Mapping[str, JSONValue] | None]] = field(default_factory=list)
    mcp: list[tuple[str, str, Mapping[str, JSONValue]]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.native) + len(self.retrieval) + len(self.mcp)


def native(
    pack: str,
    name: str,
    calls: Calls,
    *,
    result: object = None,
    delay: float = 0.0,
    error: Exception | None = None,
    mutates: bool = False,
    parameters: Mapping[str, JSONValue] = TEXT_SCHEMA,
    description: str | None = None,
    before: Callable[[], Awaitable[None]] | None = None,
) -> PackTool:
    async def handler(invocation: ToolInvocation) -> object:
        calls.native.append((f"{pack}.{name}", invocation))
        if before is not None:
            await before()
        if delay:
            await asyncio.sleep(delay)
        if error is not None:
            raise error
        return result if result is not None else invocation.arguments.get("texto", "")

    spec = ToolSpec(
        name=name,
        description=description or f"tool {name} do pack {pack}",
        parameters=parameters,
        kind="native",
        mutates=mutates,
        handler=handler,
    )
    return PackTool(name=f"{pack}.{name}", pack=pack, spec=spec)


class RecordingRetriever:
    def __init__(self, name: str, calls: Calls, chunks: Sequence[Chunk] = ()) -> None:
        self._name = name
        self._calls = calls
        self._chunks = tuple(chunks)

    async def search(
        self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None
    ) -> Sequence[Chunk]:
        self._calls.retrieval.append((self._name, query, top_k, filters))
        return self._chunks[:top_k]


def chunk(n: int = 1, *, text: str = "trecho", section: str | None = "Seção 1", page: int | None = 3) -> Chunk:
    return Chunk(chunk_id=f"c{n}", text=f"{text} {n}", score=0.9, document=f"doc-{n}", section=section, page=page)


def retrieval(
    pack: str, name: str, calls: Calls, *, collections: Sequence[str] = ("docs",), chunks: Sequence[Chunk] = ()
) -> PackTool:
    named = NamedRetriever(
        name=name,
        description=f"busca {name}",
        collections=frozenset(collections),
        retriever=RecordingRetriever(f"{pack}.{name}", calls, chunks or (chunk(1), chunk(2))),
    )
    return PackTool(name=f"{pack}.{name}", pack=pack, spec=retrieval_tool_spec(named), retriever=named)


# --- cliente MCP programado (a forma do seam `McpClients` da 007) -----------------------------------------------------


@dataclass(slots=True, kw_only=True)
class FakeServer:
    tools: Sequence[ToolSpec] = ()
    failure: str | None = None
    results: Mapping[str, ToolResult] = field(default_factory=dict)
    delay: float = 0.0


def mcp_tool(name: str, *, mutates: bool = False, parameters: Mapping[str, JSONValue] = TEXT_SCHEMA) -> ToolSpec:
    return ToolSpec(name=name, description=f"tool MCP {name}", parameters=parameters, kind="mcp", mutates=mutates)


class FakeMcpClient:
    def __init__(self, servers: Mapping[str, FakeServer], aliases: frozenset[str], calls: Calls, log: list[str]):
        self._servers = servers
        self._aliases = aliases
        self._calls = calls
        self._log = log

    async def discover(self, aliases: Sequence[str]) -> Discovery:
        tools: list[ToolSpec] = []
        unavailable: dict[str, str] = {}
        for alias in aliases:
            self._log.append(alias)
            if alias not in self._aliases or alias not in self._servers:
                raise UnknownServer(alias)
            server = self._servers[alias]
            if server.failure is not None:
                unavailable[alias] = server.failure
            else:
                tools.extend(server.tools)
        return Discovery(tools=tuple(tools), unavailable=unavailable)

    async def discover_tools(self, aliases: Sequence[str]) -> Sequence[ToolSpec]:
        return (await self.discover(aliases)).tools

    async def execute(self, alias: str, tool: str, arguments: Mapping[str, JSONValue]) -> ToolResult:
        self._calls.mcp.append((alias, tool, arguments))
        server = self._servers[alias]
        if server.delay:
            await asyncio.sleep(server.delay)
        if tool in server.results:
            return server.results[tool]
        return ToolResult(content=json.dumps(dict(arguments), sort_keys=True, ensure_ascii=False))


class FakeMcpClients:
    def __init__(self, servers: Mapping[str, FakeServer] | None = None, calls: Calls | None = None) -> None:
        self.servers = dict(servers or {})
        self.calls = calls or Calls()
        self.discovered: list[str] = []

    def client_for(self, grant: ExecutionGrant) -> FakeMcpClient:
        return FakeMcpClient(self.servers, frozenset(grant.mcp_aliases), self.calls, self.discovered)


# --- a sessão montada -------------------------------------------------------------------------------------------------


@dataclass(slots=True, kw_only=True)
class Kit:
    service: Any
    trace: RecordingTraceSink
    audit: AuditLog
    mcp: FakeMcpClients
    clock: FakeClock
    calls: Calls


def build(
    *,
    tools: Sequence[PackTool] = (),
    servers: Mapping[str, FakeServer] | None = None,
    calls: Calls | None = None,
    audit: AuditLog | None = None,
    limits: GatewayLimits | None = None,
    clock: FakeClock | None = None,
) -> Kit:
    from ai_core.capabilities.service import CapabilityService

    calls = calls or Calls()
    mcp = FakeMcpClients(servers, calls)
    trace = RecordingTraceSink()
    clock = clock or FakeClock()
    audit = audit or InMemoryAuditLog()
    service = CapabilityService(
        pack_tools=StaticPackTools(tools),
        mcp=mcp,
        audit=audit,
        trace=trace,
        clock=clock,
        limits=limits or GatewayLimits(),
    )
    return Kit(service=service, trace=trace, audit=audit, mcp=mcp, clock=clock, calls=calls)
