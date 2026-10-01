"""Adapters em memória e de teste de todas as portas da 007 (contracts/ports.md).

São o adapter em memória que o princípio XIII exige de cada porta e o que o perfil de teste da composition root usa.
Moram na distribuição, não no kit de teste, pelo mesmo motivo do provider simulado da 006: a suíte de um pack externo
sobe a plataforma de verdade com eles, sem rede.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address, ip_address

from ai_core.mcp.api import CREDENTIAL_REF_PATTERN
from ai_core.mcp.ports import (
    CachedDiscovery,
    CacheKey,
    Clock,
    McpConfig,
    OperationLimits,
    RemotePart,
    RemoteResult,
    RemoteTool,
    StoredServer,
    Target,
    TransportFailure,
)
from ai_core_contracts import JSONValue


class InMemoryServerStore:
    """Servidores num dicionário por `(dono, alias)`."""

    def __init__(self) -> None:
        self._records: dict[tuple[str | None, str], StoredServer] = {}

    async def get(self, owner: str | None, alias: str) -> StoredServer | None:
        return self._records.get((owner, alias))

    async def list(self, owner: str | None) -> Sequence[StoredServer]:
        return sorted((r for (o, _), r in self._records.items() if o == owner), key=lambda r: r.alias)

    async def all(self) -> Sequence[StoredServer]:
        return sorted(self._records.values(), key=lambda r: (r.owner or "", r.alias))

    async def insert(self, record: StoredServer) -> bool:
        key = (record.owner, record.alias)
        if key in self._records:
            return False
        self._records[key] = record
        return True

    async def replace(self, record: StoredServer) -> bool:
        key = (record.owner, record.alias)
        if key not in self._records:
            return False
        self._records[key] = record
        return True

    async def delete(self, owner: str | None, alias: str) -> bool:
        return self._records.pop((owner, alias), None) is not None


class InMemoryConfigSource:
    """Arquivo do operador já carregado — ou nenhum."""

    def __init__(self, config: McpConfig | None = None) -> None:
        self._config = config or McpConfig()

    def load(self) -> McpConfig:
        return self._config


@dataclass(slots=True, kw_only=True)
class ScriptedServer:
    """Um servidor programado: as tools que anuncia, o resultado de cada uma, falha e atraso."""

    tools: Sequence[RemoteTool] = ()
    results: Mapping[str, RemoteResult] = field(default_factory=dict)
    failure: str | None = None
    delay: float = 0.0


class ScriptedMcpTransport:
    """Servidores por endereço (endpoint ou comando). Guarda as operações recebidas em `calls`, com o `Target`, para
    que as suítes confiram cabeçalhos e ambiente. Tool sem resultado programado devolve os argumentos em JSON."""

    def __init__(self, servers: Mapping[str, ScriptedServer] | None = None) -> None:
        self.servers: dict[str, ScriptedServer] = dict(servers or {})
        self.calls: list[tuple[str, Target]] = []

    def add(self, address: str, server: ScriptedServer) -> None:
        self.servers[address] = server

    async def list_tools(self, target: Target, *, limits: OperationLimits) -> Sequence[RemoteTool]:
        self.calls.append(("list_tools", target))
        server = await self._reach(target, limits)
        return tuple(server.tools)

    async def call_tool(
        self, target: Target, name: str, arguments: Mapping[str, JSONValue], *, limits: OperationLimits
    ) -> RemoteResult:
        self.calls.append((f"call_tool:{name}", target))
        server = await self._reach(target, limits)
        if name in server.results:
            return server.results[name]
        if not any(tool.name == name for tool in server.tools):
            return RemoteResult(parts=(RemotePart(kind="text", text=f"Unknown tool: {name}"),), is_error=True)
        return RemoteResult(parts=(RemotePart(kind="text", text=json.dumps(dict(arguments), sort_keys=True)),))

    async def _reach(self, target: Target, limits: OperationLimits) -> ScriptedServer:
        address = target.endpoint if target.endpoint is not None else (target.stdio.command if target.stdio else "")
        server = self.servers.get(address)
        if server is None:
            raise TransportFailure(f"nenhum servidor em {address}")
        if server.delay:
            try:
                await asyncio.wait_for(asyncio.sleep(server.delay), limits.timeout)
            except TimeoutError:
                raise TransportFailure(f"sem resposta em {limits.timeout:g} s") from None
        if server.failure is not None:
            raise TransportFailure(server.failure)
        return server


class FixedDnsResolver:
    """Nome → IPs fixos. IP literal devolve ele mesmo; nome desconhecido devolve vazio."""

    def __init__(self, answers: Mapping[str, Sequence[str]] | None = None) -> None:
        self._answers = {name.lower(): tuple(ip_address(ip) for ip in ips) for name, ips in (answers or {}).items()}

    async def resolve(self, host: str, port: int) -> Sequence[IPv4Address | IPv6Address]:
        try:
            return (ip_address(host.strip("[]")),)
        except ValueError:
            return self._answers.get(host.lower().rstrip("."), ())


class InMemorySecretResolver:
    """Referência → valor. Fora da gramática, nada — como no adapter de ambiente."""

    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def resolve(self, ref: str) -> str | None:
        if not CREDENTIAL_REF_PATTERN.fullmatch(ref):
            return None
        return self._values.get(ref)


class InMemoryDiscoveryCache:
    """Entradas com validade pelo relógio da porta."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._entries: dict[CacheKey, tuple[datetime, CachedDiscovery]] = {}

    def get(self, key: CacheKey) -> CachedDiscovery | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires, value = entry
        if self._clock.now() >= expires:
            del self._entries[key]
            return None
        return value

    def put(self, key: CacheKey, value: CachedDiscovery, *, ttl: timedelta) -> None:
        self._entries[key] = (self._clock.now() + ttl, value)
