"""T037 — política por servidor (US5; FR-007, FR-008): allowlist, marca de escrita, prazo e teto de tamanho."""

from __future__ import annotations

import time

import pytest
from mcp_testkit import FINANCEIRO_URL, build, global_draft, grant, policy, scripted

from axon_ai.mcp.ports import RemotePart, RemoteResult, RemoteTool

pytestmark = pytest.mark.us5

CINQUENTA = tuple(RemoteTool(name=f"t{i:02d}", description=f"tool {i}") for i in range(1, 51))


async def test_de_50_anunciadas_so_as_3_da_allowlist_com_a_marca_de_escrita() -> None:
    """US5 cen. 1."""
    kit = build(servers={FINANCEIRO_URL: scripted(*CINQUENTA)})
    tres = policy(allowed_tools=("t03", "t17", "t42"), write_tools=("t42",))
    await kit.service.create_global(global_draft(policy=tres))

    descoberta = await kit.service.client_for(grant("financeiro")).discover(["financeiro"])
    assert [(tool.name, tool.mutates) for tool in descoberta.tools] == [
        ("t03", False),
        ("t17", False),
        ("t42", True),
    ]


async def test_tool_nova_anunciada_depois_continua_ausente() -> None:
    """Edge case: o servidor passa a anunciar uma tool fora da allowlist."""
    kit = build(servers={FINANCEIRO_URL: scripted(*CINQUENTA[:3])})
    await kit.service.create_global(global_draft(policy=policy(allowed_tools=("t01",), write_tools=())))
    kit.transport.add(FINANCEIRO_URL, scripted(*CINQUENTA))
    kit.clock.advance(301)

    descoberta = await kit.service.client_for(grant("financeiro")).discover(["financeiro"])
    assert [tool.name for tool in descoberta.tools] == ["t01"]


async def test_operacao_mais_lenta_que_o_prazo_volta_como_falha_no_prazo() -> None:
    kit = build(servers={FINANCEIRO_URL: scripted(delay=5.0)})
    await kit.service.create_global(global_draft(policy=policy(timeout_ms=1000)))
    client = kit.service.client_for(grant("financeiro"))

    inicio = time.monotonic()
    resultado = await client.execute("financeiro", "saldo", {})
    decorrido = time.monotonic() - inicio

    assert resultado.error == "sem resposta em 1 s"
    assert decorrido <= 1.1, f"o prazo é o da política (+10%): {decorrido:.2f} s"
    descoberta = await client.discover(["financeiro"])
    assert descoberta.unavailable["financeiro"] == "sem resposta em 1 s"


async def test_resultado_acima_do_teto_volta_cortado_com_marca() -> None:
    grande = RemoteResult(parts=(RemotePart(kind="text", text="z" * 10_000),))
    kit = build(servers={FINANCEIRO_URL: scripted(results={"saldo": grande})})
    await kit.service.create_global(global_draft(policy=policy(max_response_bytes=2048)))

    resultado = await kit.service.client_for(grant("financeiro")).execute("financeiro", "saldo", {})
    assert resultado.truncated and isinstance(resultado.content, str)
    assert len(resultado.content.encode("utf-8")) <= 2048
    assert "resposta cortada" in resultado.content


async def test_os_limites_chegam_ao_transporte() -> None:
    """R6: o prazo é regra da porta (o serviço só repassa); o teto do transporte é o da política + 1 MiB."""
    from axon_ai.mcp.ports import OperationLimits

    received: list[OperationLimits] = []

    class Spy:
        async def list_tools(self, target: object, *, limits: OperationLimits) -> list[RemoteTool]:
            received.append(limits)
            return []

        async def call_tool(self, *_args: object, limits: OperationLimits) -> RemoteResult:
            received.append(limits)
            return RemoteResult()

    spy = Spy()
    kit = build(transports={"http": spy, "sse": spy, "stdio": spy})
    await kit.service.create_global(global_draft(policy=policy(timeout_ms=7000, max_response_bytes=4096)))
    await kit.service.client_for(grant("financeiro")).discover(["financeiro"])
    assert received == [OperationLimits(timeout=7.0, max_bytes=4096 + 1_048_576)]
