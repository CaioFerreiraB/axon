"""T042 — o backend de rede do transporte HTTP, com conector falso (contracts/network-policy.md, "Onde é aplicada").

Com servidor local não há como uma primeira resolução ser pública; aqui o conector é falso, e o que se confere é que
cada conexão resolve, decide e conecta **no IP validado** — nunca no nome.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any

import httpcore2
import pytest

from ai_core.mcp.adapters.transport_http import GuardedNetworkBackend

pytestmark = pytest.mark.us6


class FlipResolver:
    """Cada chamada devolve a próxima resposta: é o rebinding."""

    def __init__(self, *answers: Sequence[str]) -> None:
        self._answers = [tuple(ip_address(ip) for ip in answer) for answer in answers]

    async def resolve(self, host: str, port: int) -> Sequence[IPv4Address | IPv6Address]:
        return self._answers.pop(0)


class FakeStream(httpcore2.AsyncNetworkStream):
    def __init__(self, data: bytes = b"") -> None:
        self._data = data

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        chunk, self._data = self._data[:max_bytes], self._data[max_bytes:]
        return chunk

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        return None

    async def aclose(self) -> None:
        return None

    def get_extra_info(self, info: str) -> Any:
        return None


class FakeConnector:
    def __init__(self, data: bytes = b"") -> None:
        self.calls: list[tuple[str, int]] = []
        self._data = data

    async def __call__(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        self.calls.append((host, port))
        return FakeStream(self._data)


def backend(resolver: Any, connector: FakeConnector, **overrides: Any) -> GuardedNetworkBackend:
    options: dict[str, Any] = {
        "dns": resolver,
        "scope": "user",
        "internal_hosts": frozenset(),
        "allowed_hosts": None,
        "max_bytes": 10_000,
        "connector": connector,
    }
    return GuardedNetworkBackend(**(options | overrides))


async def test_conecta_no_ip_validado_e_nao_no_nome() -> None:
    connector = FakeConnector()
    await backend(FlipResolver(["93.184.216.34"]), connector).connect_tcp("mcp.example", 443)
    assert connector.calls == [("93.184.216.34", 443)]


async def test_rebinding_a_segunda_conexao_e_bloqueada_antes_do_conector() -> None:
    connector = FakeConnector()
    guarded = backend(FlipResolver(["93.184.216.34"], ["10.0.0.7"]), connector)

    await guarded.connect_tcp("rebind.example", 443)
    with pytest.raises(httpcore2.ConnectError):
        await guarded.connect_tcp("rebind.example", 443)

    assert connector.calls == [("93.184.216.34", 443)], "o conector nunca viu o IP privado"
    assert guarded.violation is not None and "10.0.0.7" in guarded.violation


async def test_allowlist_de_destino_aplicada_a_cada_conexao() -> None:
    connector = FakeConnector()
    guarded = backend(
        FlipResolver(["93.184.216.34"], ["93.184.216.34"]),
        connector,
        allowed_hosts=frozenset({"*.empresa.example"}),
    )
    await guarded.connect_tcp("mcp.empresa.example", 443)
    with pytest.raises(httpcore2.ConnectError):
        await guarded.connect_tcp("outro.example", 443)
    assert connector.calls == [("93.184.216.34", 443)]
    assert guarded.violation is not None and "allowlist" in guarded.violation


async def test_teto_de_bytes_somado_entre_as_conexoes_da_operacao() -> None:
    connector = FakeConnector(data=b"x" * 600)
    guarded = backend(FlipResolver(["93.184.216.34"], ["93.184.216.34"]), connector, max_bytes=1000)

    first = await guarded.connect_tcp("mcp.example", 443)
    assert len(await first.read(10_000)) == 600
    second = await guarded.connect_tcp("mcp.example", 443)
    with pytest.raises(httpcore2.ReadError):
        await second.read(10_000)
    assert guarded.violation is not None and "1000 bytes" in guarded.violation


async def test_socket_unix_e_recusado() -> None:
    guarded = backend(FlipResolver(), FakeConnector())
    with pytest.raises(httpcore2.ConnectError):
        await guarded.connect_unix_socket("/var/run/docker.sock")
