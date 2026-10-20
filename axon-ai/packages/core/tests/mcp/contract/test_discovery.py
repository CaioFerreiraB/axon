"""T013 — descoberta com cache por TTL, filtrada pela allowlist (FR-002, FR-007, FR-010, SC-003; research R8)."""

from __future__ import annotations

import pytest
from mcp_testkit import FINANCEIRO_URL, build, global_draft, grant, operations, policy, scripted

from axon_ai.mcp.api import UnknownServer
from axon_ai.mcp.ports import RemoteTool

pytestmark = pytest.mark.us1


async def test_mcp_registrado_aparece_na_descoberta_seguinte_sem_restart() -> None:
    """US1 cen. 1, SC-003: o serviço já está montado; nada é recriado."""
    kit = build()
    client = kit.service.client_for(grant("financeiro"))
    with pytest.raises(UnknownServer):
        await client.discover(["financeiro"])

    await kit.service.create_global(global_draft())
    descoberta = await kit.service.client_for(grant("financeiro")).discover(["financeiro"])

    assert [tool.name for tool in descoberta.tools] == ["saldo", "extrato", "pagar"]
    assert dict(descoberta.unavailable) == {}


async def test_so_a_allowlist_com_nome_local_kind_mcp_e_marca_de_escrita() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    descoberta = await kit.service.client_for(grant("financeiro")).discover(["financeiro"])

    assert "secreta" not in [tool.name for tool in descoberta.tools], "anunciada fora da allowlist"
    for tool in descoberta.tools:
        assert tool.kind == "mcp" and tool.handler is None
        assert tool.mutates is (tool.name == "pagar")
    assert descoberta.tools[0].description == "Saldo da conta"


async def test_tool_da_allowlist_nao_anunciada_nao_aparece() -> None:
    kit = build()
    await kit.service.create_global(global_draft(policy=policy(allowed_tools=("saldo", "sumiu"), write_tools=())))
    descoberta = await kit.service.client_for(grant("financeiro")).discover(["financeiro"])
    assert [tool.name for tool in descoberta.tools] == ["saldo"]


async def test_descricao_vazia_vira_o_nome() -> None:
    kit = build(servers={FINANCEIRO_URL: scripted(RemoteTool(name="saldo", description=None))})
    await kit.service.create_global(global_draft(policy=policy(allowed_tools=("saldo",), write_tools=())))
    (tool,) = (await kit.service.client_for(grant("financeiro")).discover(["financeiro"])).tools
    assert tool.description == "saldo"


async def test_cache_dentro_e_depois_do_ttl() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    client = kit.service.client_for(grant("financeiro"))

    await client.discover(["financeiro"])
    await client.discover(["financeiro"])
    assert operations(kit.transport).count("list_tools") == 1, "dentro do TTL não toca o servidor"
    kit.clock.advance(301)
    await client.discover(["financeiro"])
    assert operations(kit.transport).count("list_tools") == 2


async def test_alterar_o_registro_invalida_e_a_politica_nova_vale_na_hora() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    client = kit.service.client_for(grant("financeiro"))
    await client.discover(["financeiro"])

    kit.clock.advance(1)
    await kit.service.update_global("financeiro", global_draft(policy=policy(allowed_tools=("saldo",), write_tools=())))
    descoberta = await kit.service.client_for(grant("financeiro")).discover(["financeiro"])
    assert [tool.name for tool in descoberta.tools] == ["saldo"]
    assert operations(kit.transport).count("list_tools") == 2, "a versão do registro mudou"


async def test_servidor_com_falha_fica_em_unavailable_e_os_demais_atendem() -> None:
    kit = build(servers={"https://quebrado.example/mcp": scripted(failure="conexão recusada")})
    await kit.service.create_global(global_draft())
    await kit.service.create_global(global_draft(alias="quebrado", endpoint="https://quebrado.example/mcp"))

    descoberta = await kit.service.client_for(grant("financeiro", "quebrado")).discover(["financeiro", "quebrado"])
    assert {tool.name for tool in descoberta.tools} == {"saldo", "extrato", "pagar"}
    assert dict(descoberta.unavailable) == {"quebrado": "conexão recusada"}


async def test_falha_fica_30_segundos_em_cache_negativo() -> None:
    kit = build(servers={FINANCEIRO_URL: scripted(failure="fora do ar")})
    await kit.service.create_global(global_draft())
    client = kit.service.client_for(grant("financeiro"))

    await client.discover(["financeiro"])
    kit.clock.advance(29)
    await client.discover(["financeiro"])
    assert operations(kit.transport).count("list_tools") == 1
    kit.clock.advance(2)
    await client.discover(["financeiro"])
    assert operations(kit.transport).count("list_tools") == 2


async def test_discover_tools_devolve_so_as_tools() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    tools = await kit.service.client_for(grant("financeiro")).discover_tools(["financeiro"])
    assert [tool.name for tool in tools] == ["saldo", "extrato", "pagar"]
