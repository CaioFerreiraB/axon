"""T033 — isolamento entre usuários (SC-004; FR-006; US4): nenhum MCP de usuário vaza para outro."""

from __future__ import annotations

import pytest
from mcp_testkit import ANA, BIA, build, global_draft, grant, user_draft

from ai_core.mcp.api import NOT_FOUND_MESSAGE, McpNotFound, UnknownServer

pytestmark = pytest.mark.us4


async def test_b_nao_lista_o_mcp_de_a() -> None:
    """US4 cen. 1."""
    kit = build()
    await kit.service.create_mine(ANA, user_draft())
    assert await kit.service.mine(BIA) == []
    assert [s.alias for s in await kit.service.available(BIA)] == []


async def test_b_nao_le_altera_nem_apaga_o_mcp_de_a_e_a_resposta_e_a_de_inexistente() -> None:
    kit = build()
    await kit.service.create_mine(ANA, user_draft())

    mensagens = []
    for operacao in (
        lambda: kit.service.get_mine(BIA, "~drive"),
        lambda: kit.service.update_mine(BIA, "~drive", user_draft()),
        lambda: kit.service.delete_mine(BIA, "~drive"),
        lambda: kit.service.get_mine(BIA, "~nao-existe"),
        lambda: kit.service.get_mine(BIA, "nem-til"),
    ):
        with pytest.raises(McpNotFound) as caught:
            await operacao()
        mensagens.append(str(caught.value))
    assert set(mensagens) == {NOT_FOUND_MESSAGE}, "alheio e inexistente são indistinguíveis"
    assert [s.alias for s in await kit.service.mine(ANA)] == ["~drive"], "nada mudou para A"


async def test_o_cliente_de_b_nao_alcanca_o_mcp_de_a_mesmo_com_o_alias_no_grant() -> None:
    kit = build()
    await kit.service.create_mine(ANA, user_draft())
    cliente_da_bia = kit.service.client_for(grant("~drive", assistant="~dela", principal=BIA))
    with pytest.raises(UnknownServer):
        await cliente_da_bia.discover(["~drive"])
    with pytest.raises(UnknownServer):
        await cliente_da_bia.execute("~drive", "saldo", {})
    assert kit.transport.calls == []


async def test_b_pode_ter_um_mcp_com_o_mesmo_nome_e_cada_um_ve_o_seu() -> None:
    kit = build()
    await kit.service.create_mine(ANA, user_draft(description="da Ana"))
    await kit.service.create_mine(BIA, user_draft(description="da Bia"))
    assert (await kit.service.get_mine(ANA, "~drive")).description == "da Ana"
    assert (await kit.service.get_mine(BIA, "~drive")).description == "da Bia"


async def test_global_drive_e_drive_de_usuario_coexistem_no_cliente() -> None:
    """US4 cen. 5: `drive` e `~drive` nunca se confundem."""
    kit = build()
    await kit.service.create_global(global_draft(alias="drive", user_access=True))
    await kit.service.create_mine(ANA, user_draft())
    client = kit.service.client_for(grant("drive", "~drive", assistant="~meu", principal=ANA))
    descoberta = await client.discover(["drive", "~drive"])
    assert dict(descoberta.unavailable) == {} and len(descoberta.tools) == 6
