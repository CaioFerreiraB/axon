"""T043 — suíte de SSRF de ponta a ponta pelo transporte HTTP real (SC-002; US6; contracts/network-policy.md).

O servidor de demonstração escuta em `127.0.0.1` e conta as requisições que recebe: um vetor bloqueado não pode
produzir nenhuma. Os nomes de teste resolvem por um `DnsResolver` fixo. O rebinding está em
`contract/test_guarded_backend.py` — com servidor local não há como a primeira resolução ser pública.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from mcp_testkit import serving
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Route

from ai_core.mcp.adapters.memory import FixedDnsResolver
from ai_core.mcp.adapters.transport_http import HttpMcpTransport
from ai_core.mcp.ports import OperationLimits, Target, TransportFailure

pytestmark = pytest.mark.us6

LIMITS = OperationLimits(timeout=10.0, max_bytes=2_000_000)
PUBLICO = "93.184.216.34"


class Counter:
    """App ASGI que conta as requisições e repassa à app de demonstração."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.hits = 0

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            self.hits += 1
        await self.app(scope, receive, send)


@pytest.fixture
def demo() -> Iterator[tuple[int, Counter]]:
    from servers.demo import http_app

    counter = Counter(http_app())
    with serving(counter) as port:
        yield port, counter


def transport(*, internal: frozenset[str] = frozenset(), allowed: frozenset[str] | None = None) -> HttpMcpTransport:
    dns = FixedDnsResolver(
        {
            "interno.exemplo.test": ["127.0.0.1"],
            "misto.exemplo.test": [PUBLICO, "127.0.0.1"],
            "2130706433": ["127.0.0.1"],
            "0177.0.0.1": ["127.0.0.1"],
            "api.localhost": ["127.0.0.1"],
            "outro.example": [PUBLICO],
        }
    )
    return HttpMcpTransport(dns=dns, internal_hosts=internal, allowed_hosts=allowed)


def target(endpoint: str, *, scope: str = "user") -> Target:
    return Target(alias="x", scope=scope, transport="http", endpoint=endpoint)  # type: ignore[arg-type]


async def blocked(endpoint: str, *, scope: str = "user", **options: Any) -> str:
    with pytest.raises(TransportFailure) as caught:
        await transport(**options).list_tools(target(endpoint, scope=scope), limits=LIMITS)
    return caught.value.reason


@pytest.mark.parametrize(
    "host",
    [
        "interno.exemplo.test",
        "misto.exemplo.test",
        "127.0.0.1",
        "[::ffff:127.0.0.1]",
        "2130706433",
        "0177.0.0.1",
        "localhost",
        "api.localhost",
    ],
)
@pytest.mark.parametrize("scope", ["user", "global"])
async def test_vetores_nao_chegam_ao_servidor(demo: tuple[int, Counter], host: str, scope: str) -> None:
    """US6 cen. 1: o host resolve para faixa privada (ou é ela) — nenhuma requisição chega."""
    port, counter = demo
    await blocked(f"http://{host}:{port}/mcp", scope=scope)
    assert counter.hits == 0


async def test_metadados_por_global_registrado_pela_api() -> None:
    """US6 cen. 4: bloqueado antes de qualquer conexão — o endereço nem precisa existir."""
    reason = await blocked("http://169.254.169.254/latest/meta-data", scope="global")
    assert "link-local" in reason


async def test_host_publico_fora_da_allowlist_de_destino() -> None:
    """US6 cen. 5: bloqueado pela allowlist antes de conectar, para global e para usuário."""
    for scope in ("user", "global"):
        reason = await blocked("https://outro.example/mcp", scope=scope, allowed=frozenset({"*.empresa.example"}))
        assert "allowlist" in reason


async def test_host_interno_so_para_global(demo: tuple[int, Counter]) -> None:
    """US6 cen. 3."""
    port, counter = demo
    internos = frozenset({"interno.exemplo.test"})
    tools = await transport(internal=internos).list_tools(
        target(f"http://interno.exemplo.test:{port}/mcp", scope="global"), limits=LIMITS
    )
    assert any(tool.name == "ecoar" for tool in tools) and counter.hits > 0

    hits = counter.hits
    await blocked(f"http://interno.exemplo.test:{port}/mcp", scope="user", internal=internos)
    assert counter.hits == hits


@pytest.fixture
def redirector(demo: tuple[int, Counter]) -> Iterator[tuple[int, Counter]]:
    """Servidor que responde 302 para o servidor de demonstração, por IP e por um nome que resolve para privada."""
    demo_port, counter = demo

    async def to_ip(_request: Request) -> RedirectResponse:
        return RedirectResponse(f"http://127.0.0.1:{demo_port}/mcp", status_code=302)

    async def to_name(_request: Request) -> RedirectResponse:
        return RedirectResponse(f"http://interno.exemplo.test:{demo_port}/mcp", status_code=307)

    methods = ["GET", "POST"]
    app = Starlette(routes=[Route("/ip", to_ip, methods=methods), Route("/nome", to_name, methods=methods)])
    with serving(app) as port:
        yield port, counter


@pytest.mark.parametrize("path", ["ip", "nome"])
async def test_redirecionamento_para_o_destino_bloqueado_nao_chega(redirector: tuple[int, Counter], path: str) -> None:
    """US6 cen. 2: o redirecionador é global e liberado; o destino do redirecionamento, não."""
    port, counter = redirector
    with pytest.raises(TransportFailure):
        await transport(internal=frozenset({"127.0.0.1"})).list_tools(
            target(f"http://127.0.0.1:{port}/{path}", scope="global"), limits=LIMITS
        )
    assert counter.hits == 0, "nem o 302 por IP nem o 307 por nome levaram a requisição ao servidor"


async def test_proxy_do_ambiente_e_ignorado(demo: tuple[int, Counter], monkeypatch: pytest.MonkeyPatch) -> None:
    """Um proxy faria a conexão real sair de outro lugar, por fora da política: `trust_env` desligado."""
    port, counter = demo
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")
    tools = await transport(internal=frozenset({"127.0.0.1"})).list_tools(
        target(f"http://127.0.0.1:{port}/mcp", scope="global"), limits=LIMITS
    )
    assert tools and counter.hits > 0
