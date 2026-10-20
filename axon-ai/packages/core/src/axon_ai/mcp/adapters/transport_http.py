"""`McpTransport` por `http` (Streamable HTTP) e `sse` (HTTP+SSE legado), com a política de rede aplicada a cada
conexão (research R5, R6; contracts/network-policy.md).

O backend de rede do `httpcore2` resolve o nome pelo `DnsResolver`, pede a decisão a `domain/network.py` e abre o TCP
**no IP que ela devolve** — a biblioteca nunca resolve de novo, o que fecha o DNS rebinding. O TLS continua verificando
o certificado contra o nome do host. Toda conexão da operação passa por ele, inclusive as de redirecionamento (o SDK
só segue os da mesma origem), e ele soma os bytes lidos contra o teto da operação. Proxies do ambiente ficam
desligados: um proxy faria a conexão real sair de outro lugar, por fora da política.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import httpcore2
import httpx2
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

from axon_ai.mcp.adapters import sdk_session
from axon_ai.mcp.api import Scope
from axon_ai.mcp.domain.network import admit
from axon_ai.mcp.ports import DnsResolver, OperationLimits, RemoteResult, RemoteTool, Target, TransportFailure
from axon_ai_contracts import JSONValue

Connector = Callable[..., Awaitable[httpcore2.AsyncNetworkStream]]
"""Abre o TCP num endereço já validado: `(host, port, timeout, local_address, socket_options)`."""


class GuardedNetworkBackend(httpcore2.AsyncNetworkBackend):
    """Uma instância por operação: guarda o motivo da primeira violação e o saldo de bytes da operação inteira."""

    def __init__(
        self,
        *,
        dns: DnsResolver,
        scope: Scope,
        internal_hosts: frozenset[str],
        allowed_hosts: frozenset[str] | None,
        max_bytes: int,
        connector: Connector | None = None,
    ) -> None:
        self._dns = dns
        self._scope = scope
        self._internal_hosts = internal_hosts
        self._allowed_hosts = allowed_hosts
        self._max_bytes = max_bytes
        self._remaining = max_bytes
        self._inner = httpcore2.AnyIOBackend()
        self._connect: Connector = connector or self._inner.connect_tcp
        self.violation: str | None = None

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        addresses = await self._dns.resolve(host, port)
        admission = admit(
            host,
            addresses,
            scope=self._scope,
            internal_hosts=self._internal_hosts,
            allowed_hosts=self._allowed_hosts,
        )
        if not admission.allowed or admission.address is None:
            self.violation = self.violation or admission.reason or "destino bloqueado"
            raise httpcore2.ConnectError(self.violation)
        stream = await self._connect(str(admission.address), port, timeout, local_address, socket_options)
        return _CountingStream(stream, self)

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: Iterable[Any] | None = None
    ) -> httpcore2.AsyncNetworkStream:
        self.violation = self.violation or "destino bloqueado: socket unix não é destino de MCP"
        raise httpcore2.ConnectError(self.violation)

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)

    def spend(self, size: int) -> None:
        self._remaining -= size
        if self._remaining < 0:
            self.violation = self.violation or f"resposta acima do teto de {self._max_bytes} bytes"
            raise httpcore2.ReadError(self.violation)


class _CountingStream(httpcore2.AsyncNetworkStream):
    def __init__(self, inner: httpcore2.AsyncNetworkStream, backend: GuardedNetworkBackend) -> None:
        self._inner = inner
        self._backend = backend

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        data = await self._inner.read(max_bytes, timeout)
        self._backend.spend(len(data))
        return data

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        await self._inner.write(buffer, timeout)

    async def aclose(self) -> None:
        await self._inner.aclose()

    async def start_tls(
        self, ssl_context: Any, server_hostname: str | None = None, timeout: float | None = None
    ) -> httpcore2.AsyncNetworkStream:
        return _CountingStream(await self._inner.start_tls(ssl_context, server_hostname, timeout), self._backend)

    def get_extra_info(self, info: str) -> Any:
        return self._inner.get_extra_info(info)


class _GuardedTransport(httpx2.AsyncHTTPTransport):
    """O transporte do `httpx2` com o pool do `httpcore2` sobre o backend guardado."""

    def __init__(self, backend: GuardedNetworkBackend) -> None:
        super().__init__(trust_env=False)
        self._pool = httpcore2.AsyncConnectionPool(
            ssl_context=httpx2.create_ssl_context(trust_env=False), network_backend=backend
        )


class HttpMcpTransport:
    def __init__(
        self,
        *,
        dns: DnsResolver,
        internal_hosts: frozenset[str],
        allowed_hosts: frozenset[str] | None,
        connector: Connector | None = None,
    ) -> None:
        self._dns = dns
        self._internal_hosts = internal_hosts
        self._allowed_hosts = allowed_hosts
        self._connector = connector

    async def list_tools(self, target: Target, *, limits: OperationLimits) -> Sequence[RemoteTool]:
        backend = self._backend(target, limits)
        return await sdk_session.list_tools(
            lambda: self._open(target, backend, limits), limits=limits, explain=_explain(backend)
        )

    async def call_tool(
        self, target: Target, name: str, arguments: Mapping[str, JSONValue], *, limits: OperationLimits
    ) -> RemoteResult:
        backend = self._backend(target, limits)
        return await sdk_session.call_tool(
            lambda: self._open(target, backend, limits), name, arguments, limits=limits, explain=_explain(backend)
        )

    def _backend(self, target: Target, limits: OperationLimits) -> GuardedNetworkBackend:
        if target.endpoint is None:
            raise TransportFailure(f"'{target.alias}' não tem endpoint")
        return GuardedNetworkBackend(
            dns=self._dns,
            scope=target.scope,
            internal_hosts=self._internal_hosts,
            allowed_hosts=self._allowed_hosts,
            max_bytes=limits.max_bytes,
            connector=self._connector,
        )

    @staticmethod
    def _open(
        target: Target, backend: GuardedNetworkBackend, limits: OperationLimits
    ) -> AbstractAsyncContextManager[Any]:
        endpoint = target.endpoint or ""
        headers = dict(target.headers)
        timeout = httpx2.Timeout(limits.timeout)

        def client(
            headers: Mapping[str, str] | None = None, timeout: httpx2.Timeout | None = None, auth: Any = None
        ) -> httpx2.AsyncClient:
            return httpx2.AsyncClient(
                transport=_GuardedTransport(backend),
                headers=dict(headers or {}),
                timeout=timeout,
                auth=auth,
                trust_env=False,
                follow_redirects=False,
            )

        if target.transport == "sse":
            return sse_client(
                endpoint,
                headers=headers,
                timeout=limits.timeout,
                sse_read_timeout=limits.timeout,
                httpx_client_factory=client,
            )

        @asynccontextmanager
        async def streamable() -> AsyncIterator[Any]:
            async with client(headers, timeout) as http, streamable_http_client(endpoint, http_client=http) as streams:
                yield streams

        return streamable()


def _explain(backend: GuardedNetworkBackend) -> sdk_session.Explain:
    return lambda _error: backend.violation
