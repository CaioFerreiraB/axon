"""T019 — a sessão com o cliente MCP real da 007 contra o servidor de demonstração dela (`servers.demo`)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from capabilities_testkit import FakeClock, RecordingTraceSink, context, grant

from axon_ai.capabilities.adapters.memory import InMemoryAuditLog, StaticPackTools
from axon_ai.capabilities.api import GatewayLimits, ToolCall
from axon_ai.capabilities.service import CapabilityService
from axon_ai.mcp.adapters.memory import (
    FixedDnsResolver,
    InMemoryDiscoveryCache,
    InMemorySecretResolver,
    InMemoryServerStore,
)
from axon_ai.mcp.adapters.transport_http import HttpMcpTransport
from axon_ai.mcp.api import McpServerDraft, SecurityPolicy
from axon_ai.mcp.ports import McpConfig
from axon_ai.mcp.service import McpService

pytestmark = pytest.mark.us2


@pytest.fixture
def demo() -> Iterator[str]:
    from mcp_testkit import serving
    from servers.demo import http_app

    with serving(http_app()) as port:
        yield f"http://127.0.0.1:{port}/mcp"


async def test_tools_do_servidor_real_com_namespace_executadas_pelo_cliente_restrito(demo: str) -> None:
    clock = FakeClock()
    transport = HttpMcpTransport(dns=FixedDnsResolver(), internal_hosts=frozenset({"127.0.0.1"}), allowed_hosts=None)
    mcp = McpService(
        store=InMemoryServerStore(),
        config=McpConfig(internal_hosts=frozenset({"127.0.0.1"})),
        transports={"http": transport, "sse": transport},
        secrets=InMemorySecretResolver(),
        cache=InMemoryDiscoveryCache(clock),
        clock=clock,
    )
    await mcp.create_global(
        McpServerDraft(
            alias="demo", transport="http", endpoint=demo, policy=SecurityPolicy(allowed_tools=("ecoar", "grande"))
        )
    )
    capabilities = CapabilityService(
        pack_tools=StaticPackTools(),
        mcp=mcp,
        audit=InMemoryAuditLog(),
        trace=RecordingTraceSink(),
        clock=clock,
        limits=GatewayLimits(max_response_bytes=2048),
    )

    session = await capabilities.open(grant(mcp=["demo"]), context())
    assert list(session.tools) == ["demo.ecoar", "demo.grande"], "só a allowlist do servidor, com o alias"

    eco = await session.execute(ToolCall(name="demo.ecoar", arguments={"texto": "olá"}))
    assert eco.status == "ok" and "\nolá\n" in eco.text
    grande = await session.execute(ToolCall(name="demo.grande", arguments={"n": 10_000}))
    assert grande.status == "ok" and grande.truncated
    quem = await session.execute(ToolCall(name="demo.quem", arguments={}))
    assert quem.status == "unknown", "fora da allowlist do servidor, fora do catálogo"
