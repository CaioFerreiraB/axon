"""T024 — varredura de segredos (SC-001; US2 cen. 1): o banco e os logs depois de operações autenticadas.

Pelo transporte HTTP real, contra o servidor de demonstração — o segredo de fato atravessa o processo e chega ao
servidor (que devolve só o hash do cabeçalho, para não trazê-lo de volta na resposta), e mesmo assim não aparece no
armazenamento nem em log nenhum, nem com os loggers do SDK e do `httpcore2` em DEBUG.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import pytest
from mcp_testkit import grant, policy

from axon_ai.mcp.adapters.memory import FixedDnsResolver, InMemoryDiscoveryCache, InMemorySecretResolver
from axon_ai.mcp.api import McpServerDraft
from axon_ai.mcp.ports import McpConfig
from axon_ai.mcp.service import McpService

pytestmark = pytest.mark.us2

SEGREDO = "s3cr3t-que-nao-pode-vazar-7f1c"


async def test_nem_o_banco_nem_os_logs_contem_o_segredo(
    pg_pool: Any, demo_http: str, caplog: pytest.LogCaptureFixture
) -> None:
    from mcp_testkit import MutableClock

    from axon_ai.mcp.adapters.registry_postgres import PostgresServerStore
    from axon_ai.mcp.adapters.transport_http import HttpMcpTransport

    caplog.set_level(logging.DEBUG)
    clock = MutableClock()
    transport = HttpMcpTransport(dns=FixedDnsResolver(), internal_hosts=frozenset({"127.0.0.1"}), allowed_hosts=None)
    service = McpService(
        store=PostgresServerStore(pg_pool),
        config=McpConfig(internal_hosts=frozenset({"127.0.0.1"})),
        transports={"http": transport, "sse": transport},
        secrets=InMemorySecretResolver({"demo_token": SEGREDO}),
        cache=InMemoryDiscoveryCache(clock),
        clock=clock,
    )
    draft = McpServerDraft(
        alias="demo",
        transport="http",
        endpoint=demo_http,
        auth_type="bearer",
        credential_ref="demo_token",
        policy=policy(allowed_tools=("assinatura", "ecoar"), write_tools=()),
    )
    await service.create_global(draft)
    client = service.client_for(grant("demo"))
    await client.discover(["demo"])
    assinatura = await client.execute("demo", "assinatura", {})
    esperado = hashlib.sha256(f"Bearer {SEGREDO}".encode()).hexdigest()
    assert assinatura.content == esperado, "o segredo chegou ao servidor: a varredura abaixo é significativa"

    async with pg_pool.connection() as connection:
        cursor = await connection.execute("SELECT row_to_json(s)::text FROM mcp.servers s")
        rows = [row[0] for row in await cursor.fetchall()]
    assert rows and all(SEGREDO not in row for row in rows)
    assert any("demo_token" in row for row in rows), "só a referência"
    assert SEGREDO not in caplog.text
