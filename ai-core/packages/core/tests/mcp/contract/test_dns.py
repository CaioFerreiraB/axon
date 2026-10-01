"""T041 — conformidade da porta `DnsResolver`: o fixo das suítes e o do sistema."""

from __future__ import annotations

from collections.abc import Callable
from ipaddress import ip_address

import pytest

from ai_core.mcp.adapters.dns_system import SystemDnsResolver
from ai_core.mcp.adapters.memory import FixedDnsResolver
from ai_core.mcp.ports import DnsResolver

pytestmark = pytest.mark.us6

Make = Callable[[], DnsResolver]
ADAPTERS = pytest.mark.parametrize(
    "make",
    [lambda: FixedDnsResolver({"localhost": ["127.0.0.1"]}), SystemDnsResolver],
    ids=["fixo", "sistema"],
)


@ADAPTERS
async def test_ip_literal_devolve_ele_mesmo(make: Make) -> None:
    assert list(await make().resolve("93.184.216.34", 443)) == [ip_address("93.184.216.34")]
    assert list(await make().resolve("::1", 443)) == [ip_address("::1")]


@ADAPTERS
async def test_localhost_resolve_para_loopback(make: Make) -> None:
    addresses = await make().resolve("localhost", 80)
    assert addresses and all(address.is_loopback for address in addresses)


@ADAPTERS
async def test_nome_inexistente_devolve_vazio_e_nao_excecao(make: Make) -> None:
    assert list(await make().resolve("nao-existe.invalid", 80)) == []
