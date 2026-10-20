"""T012 e T034 — o seam `McpCatalog`, na forma da porta `McpDirectory` da 003 (research R13)."""

from __future__ import annotations

import pytest
from mcp_testkit import ANA, BIA, build, global_draft, user_draft

from axon_ai.assistants.ports import McpDirectory
from axon_ai.mcp.domain.records import StdioCommand
from axon_ai.mcp.ports import ConfigEntry, McpConfig


@pytest.mark.us1
async def test_o_servico_tem_a_forma_da_porta_da_003() -> None:
    """Único import de internal da 003, só nesta suíte: uma cópia local da porta poderia divergir da real (mypy)."""
    kit = build()
    directory: McpDirectory = kit.service
    assert await directory.aliases(owner=None) == frozenset()


@pytest.mark.us1
async def test_globais_habilitados_e_disponiveis() -> None:
    entrada = ConfigEntry(
        alias="arquivos",
        draft=global_draft(alias="arquivos", transport="stdio", endpoint=None),
        stdio=StdioCommand(command="/bin/mcp"),
    )
    quebrada = ConfigEntry(alias="ruim", problem="campo policy: obrigatório")
    kit = build(config=McpConfig(entries=(entrada, quebrada)))
    await kit.service.create_global(global_draft())
    await kit.service.create_global(global_draft(alias="desligado", enabled=False))

    assert await kit.service.aliases(owner=None) == frozenset({"arquivos", "financeiro"})


@pytest.mark.us1
async def test_desabilitar_tira_do_catalogo() -> None:
    """US1 cen. 2: a 003 marca o Assistant como indisponível pelo caminho que já existe ("MCP desconhecido")."""
    kit = build()
    await kit.service.create_global(global_draft())
    assert "financeiro" in await kit.service.aliases(owner=None)
    await kit.service.update_global("financeiro", global_draft(enabled=False))
    assert "financeiro" not in await kit.service.aliases(owner=None)


@pytest.mark.us1
async def test_sombreado_sai_do_catalogo_e_o_do_arquivo_fica() -> None:
    first = build()
    await first.service.create_global(global_draft(alias="arquivos"))
    entrada = ConfigEntry(
        alias="arquivos",
        draft=global_draft(alias="arquivos", transport="stdio", endpoint=None),
        stdio=StdioCommand(command="/bin/mcp"),
    )
    kit = build(config=McpConfig(entries=(entrada,)), store=first.store)
    assert await kit.service.aliases(owner=None) == frozenset({"arquivos"})


@pytest.mark.us4
async def test_dono_ve_os_seus_e_os_globais_liberados() -> None:
    """US4 cen. 4: global não liberado fica fora — a 003 recusa a criação como referência inexistente."""
    kit = build()
    await kit.service.create_global(global_draft(user_access=True))
    await kit.service.create_global(global_draft(alias="interno"))
    await kit.service.create_mine(ANA, user_draft())
    await kit.service.create_mine(ANA, user_draft(alias="~parado", enabled=False))
    await kit.service.create_mine(BIA, user_draft(alias="~dela"))

    assert await kit.service.aliases(owner="user:ana") == frozenset({"~drive", "financeiro"})
    assert await kit.service.aliases(owner="user:bia") == frozenset({"~dela", "financeiro"})
    assert await kit.service.aliases(owner=None) == frozenset({"financeiro", "interno"}), "sistema não vê `~`"


@pytest.mark.us4
async def test_desligar_user_access_tira_dos_usuarios() -> None:
    kit = build()
    await kit.service.create_global(global_draft(user_access=True))
    assert "financeiro" in await kit.service.aliases(owner="user:ana")
    await kit.service.update_global("financeiro", global_draft(user_access=False))
    assert "financeiro" not in await kit.service.aliases(owner="user:ana")
