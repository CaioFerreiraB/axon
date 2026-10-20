"""T028 — o cliente restrito ao grant (US3; FR-005; research R9): elo 4 da cadeia de enforcement."""

from __future__ import annotations

import pytest
from mcp_testkit import (
    ANA,
    BIA,
    FINANCEIRO_URL,
    build,
    global_draft,
    grant,
    operations,
    policy,
    scripted,
    user_draft,
)

from axon_ai.mcp.api import UnknownServer
from axon_ai.mcp.ports import RemotePart, RemoteResult
from axon_ai_contracts import MCPClient

pytestmark = pytest.mark.us3


async def test_alias_fora_do_grant_e_servidor_desconhecido_sem_io() -> None:
    """US3 cen. 1: grant com `financeiro`; algo tenta usar `drive`."""
    kit = build()
    await kit.service.create_global(global_draft())
    await kit.service.create_global(global_draft(alias="drive"))
    client = kit.service.client_for(grant("financeiro"))

    with pytest.raises(UnknownServer, match="servidor desconhecido: drive"):
        await client.discover(["financeiro", "drive"])
    with pytest.raises(UnknownServer, match="servidor desconhecido: drive"):
        await client.execute("drive", "saldo", {})
    assert kit.transport.calls == [], "nenhuma operação sai do processo"


async def test_alias_que_deixou_de_ser_visivel_tambem() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    await kit.service.create_global(global_draft(alias="outro"))
    client = kit.service.client_for(grant("financeiro", "outro"))

    await kit.service.update_global("financeiro", global_draft(enabled=False))
    await kit.service.delete_global("outro")
    for alias in ("financeiro", "outro"):
        with pytest.raises(UnknownServer):
            await client.execute(alias, "saldo", {})


async def test_assistant_de_sistema_nao_alcanca_alias_de_usuario() -> None:
    kit = build()
    await kit.service.create_mine(ANA, user_draft())
    with pytest.raises(UnknownServer):
        await kit.service.client_for(grant("~drive", principal=ANA)).discover(["~drive"])


async def test_execute_devolve_resultado_nao_confiavel() -> None:
    resultado_remoto = RemoteResult(parts=(RemotePart(kind="text", text="R$ 10,00"),), structured={"saldo": 10})
    kit = build(servers={FINANCEIRO_URL: scripted(results={"saldo": resultado_remoto})})
    await kit.service.create_global(global_draft())

    resultado = await kit.service.client_for(grant("financeiro")).execute("financeiro", "saldo", {"conta": "1"})

    assert resultado.untrusted and resultado.error is None and not resultado.truncated
    assert resultado.content == "R$ 10,00", "texto primeiro; o estruturado só quando não há texto"


async def test_tool_fora_da_allowlist_nao_toca_o_servidor() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    resultado = await kit.service.client_for(grant("financeiro")).execute("financeiro", "secreta", {})
    assert resultado.error == "tool 'secreta' não permitida em 'financeiro'"
    assert operations(kit.transport) == []


async def test_falhas_viram_resultado_de_erro_nunca_excecao() -> None:
    erro = RemoteResult(parts=(RemotePart(kind="text", text="conta inexistente"),), is_error=True)
    kit = build(
        servers={
            FINANCEIRO_URL: scripted(results={"saldo": erro}),
            "https://lento.example/mcp": scripted(delay=5.0),
            "https://caido.example/mcp": scripted(failure="conexão recusada"),
        }
    )
    await kit.service.create_global(global_draft())
    rapida = policy(allowed_tools=("saldo",), write_tools=(), timeout_ms=1000)
    await kit.service.create_global(global_draft(alias="lento", endpoint="https://lento.example/mcp", policy=rapida))
    await kit.service.create_global(global_draft(alias="caido", endpoint="https://caido.example/mcp"))
    client = kit.service.client_for(grant("financeiro", "lento", "caido"))

    do_servidor = await client.execute("financeiro", "saldo", {})
    assert do_servidor.error == "conta inexistente" and do_servidor.content == "conta inexistente"
    lento = await client.execute("lento", "saldo", {})
    assert lento.error == "sem resposta em 1 s"
    caido = await client.execute("caido", "saldo", {})
    assert caido.error == "conexão recusada" and caido.untrusted


async def test_o_cliente_cumpre_o_contrato_mcpclient_da_001() -> None:
    kit = build()
    contrato: MCPClient = kit.service.client_for(grant())
    assert await contrato.discover_tools([]) == ()


async def test_cliente_de_assistant_de_usuario_ve_os_seus_e_os_globais_liberados() -> None:
    kit = build()
    await kit.service.create_global(global_draft(user_access=True))
    await kit.service.create_global(global_draft(alias="interno"))
    await kit.service.create_mine(ANA, user_draft())

    client = kit.service.client_for(grant("~drive", "financeiro", "interno", assistant="~meu", principal=ANA))
    descoberta = await client.discover(["~drive", "financeiro"])
    assert len(descoberta.tools) == 6
    with pytest.raises(UnknownServer):
        await client.discover(["interno"])

    da_bia = kit.service.client_for(grant("~drive", assistant="~dela", principal=BIA))
    with pytest.raises(UnknownServer):
        await da_bia.discover(["~drive"])
