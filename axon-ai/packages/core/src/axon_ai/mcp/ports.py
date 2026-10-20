"""Portas secundárias da 007 (specs/007-core-mcp-integration/contracts/ports.md).

Cada uma existe por I/O, não-determinismo ou troca prevista; nenhuma por regra pura — a política de rede é função
(`domain/network.py`), não porta. Nenhum tipo de biblioteca de infraestrutura aparece aqui.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address
from types import MappingProxyType
from typing import Protocol

from axon_ai.mcp.api import Scope, Transport
from axon_ai.mcp.domain.records import (
    ConfigEntry,
    McpConfig,
    RemotePart,
    RemoteResult,
    RemoteTool,
    StdioCommand,
    StoredServer,
)
from axon_ai_contracts import JSONValue

__all__ = [
    "CacheKey",
    "CachedDiscovery",
    "Clock",
    "ConfigEntry",
    "DiscoveryCache",
    "DnsResolver",
    "McpConfig",
    "McpConfigSource",
    "McpServerStore",
    "McpTransport",
    "OperationLimits",
    "RemotePart",
    "RemoteResult",
    "RemoteTool",
    "SecretResolver",
    "StdioCommand",
    "StoredServer",
    "Target",
    "TransportFailure",
]

type IPAddress = IPv4Address | IPv6Address


@dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    """Para onde e como conectar numa operação. Existe só durante ela: cabeçalhos e ambiente trazem o segredo já
    resolvido, por isso ficam fora do `repr` (FR-004)."""

    alias: str
    scope: Scope
    transport: Transport
    endpoint: str | None = None
    stdio: StdioCommand | None = None
    headers: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}), repr=False)
    environment: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}), repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class OperationLimits:
    """Prazo da operação inteira (segundos) e teto de bytes lidos por sessão — este só em `http`/`sse` (R6)."""

    timeout: float
    max_bytes: int


class TransportFailure(Exception):
    """A operação não completou: prazo, rede, política de rede, processo, protocolo. A mensagem nunca traz segredo."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class CacheKey:
    """Identidade do servidor **e** versão do registro: alterar ou desabilitar invalida sem lógica extra (R8)."""

    scope: Scope
    owner: str | None
    alias: str
    version: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CachedDiscovery:
    """A lista bruta do servidor — o filtro da allowlist é aplicado na leitura —, ou a falha."""

    tools: tuple[RemoteTool, ...] | None = None
    failure: str | None = None


class McpServerStore(Protocol):
    """Servidores criados pela API, por `(dono, alias)`; `owner=None` são os globais."""

    async def get(self, owner: str | None, alias: str) -> StoredServer | None: ...

    async def list(self, owner: str | None) -> Sequence[StoredServer]: ...

    async def all(self) -> Sequence[StoredServer]: ...

    async def insert(self, record: StoredServer) -> bool:
        """`False` se `(owner, alias)` já existe."""
        ...

    async def replace(self, record: StoredServer) -> bool:
        """`False` se não existe."""
        ...

    async def delete(self, owner: str | None, alias: str) -> bool:
        """`False` se não existe."""
        ...


class McpConfigSource(Protocol):
    """O arquivo do operador, lido uma vez no boot."""

    def load(self) -> McpConfig:
        """Levanta `McpConfigError` em erro de arquivo; erro de uma entrada vai para a entrada."""
        ...


class McpTransport(Protocol):
    """Uma sessão por operação. O prazo de `limits` é regra desta porta: vencido, `TransportFailure` (R6)."""

    async def list_tools(self, target: Target, *, limits: OperationLimits) -> Sequence[RemoteTool]: ...

    async def call_tool(
        self, target: Target, name: str, arguments: Mapping[str, JSONValue], *, limits: OperationLimits
    ) -> RemoteResult: ...


class DnsResolver(Protocol):
    async def resolve(self, host: str, port: int) -> Sequence[IPAddress]:
        """Os IPs do nome — IP literal devolve ele mesmo; nome que não resolve devolve vazio, não exceção."""
        ...


class SecretResolver(Protocol):
    def resolve(self, ref: str) -> str | None:
        """O valor da referência, ou `None`. Só referências na gramática alcançam algum valor."""
        ...


class DiscoveryCache(Protocol):
    def get(self, key: CacheKey) -> CachedDiscovery | None:
        """`None` se ausente ou vencida."""
        ...

    def put(self, key: CacheKey, value: CachedDiscovery, *, ttl: timedelta) -> None: ...


class Clock(Protocol):
    """Tempo (ADR-013). A 011 injeta o mesmo relógio em todos os módulos."""

    def now(self) -> datetime: ...
