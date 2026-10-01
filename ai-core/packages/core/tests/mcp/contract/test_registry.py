"""T011 e T034 — o seam `McpRegistry` (contracts/mcp-api.md): globais, arquivo, saúde e escopo de usuário."""

from __future__ import annotations

import pytest
from mcp_testkit import (
    ANA,
    BIA,
    DRIVE_URL,
    FINANCEIRO_URL,
    TOOLS,
    build,
    global_draft,
    operations,
    policy,
    scripted,
    user_draft,
)

from ai_core.mcp.api import McpConflict, McpNotFound, McpRejected
from ai_core.mcp.domain.records import StdioCommand
from ai_core.mcp.ports import ConfigEntry, McpConfig

STDIO_CMD = "/usr/local/bin/mcp-arquivos"


def arquivo(*entries: ConfigEntry) -> McpConfig:
    return McpConfig(entries=entries)


def do_arquivo(alias: str = "arquivos", **overrides: object) -> ConfigEntry:
    draft = global_draft(alias=alias, transport="stdio", endpoint=None, **overrides)
    return ConfigEntry(alias=alias, draft=draft, stdio=StdioCommand(command=STDIO_CMD))


# --- globais (T011, US1) ----------------------------------------------------------------------------------------------


@pytest.mark.us1
async def test_crud_global() -> None:
    kit = build()
    criado = await kit.service.create_global(global_draft())
    assert (criado.alias, criado.scope, criado.owner, criado.origin) == ("financeiro", "global", None, "registry")
    assert criado.created_at is not None and not criado.read_only

    assert (await kit.service.get_global("financeiro")).endpoint == FINANCEIRO_URL
    kit.clock.advance(10)
    alterado = await kit.service.update_global("financeiro", global_draft(enabled=False))
    assert not alterado.enabled and alterado.updated_at != alterado.created_at
    assert [s.alias for s in await kit.service.globals()] == ["financeiro"]

    await kit.service.delete_global("financeiro")
    with pytest.raises(McpNotFound):
        await kit.service.get_global("financeiro")
    with pytest.raises(McpNotFound):
        await kit.service.delete_global("financeiro")


@pytest.mark.us1
async def test_alias_global_repetido_e_conflito() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    with pytest.raises(McpConflict):
        await kit.service.create_global(global_draft())


@pytest.mark.us1
async def test_update_nao_renomeia() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    with pytest.raises(McpRejected) as caught:
        await kit.service.update_global("financeiro", global_draft(alias="outro"))
    assert caught.value.field == "alias"


@pytest.mark.us1
async def test_stdio_pela_api_e_recusado_em_create_e_update() -> None:
    """US1 cen. 3, FR-013."""
    kit = build()
    with pytest.raises(McpRejected) as caught:
        await kit.service.create_global(global_draft(transport="stdio", endpoint=None))
    assert caught.value.field == "transport"
    await kit.service.create_global(global_draft())
    with pytest.raises(McpRejected) as caught:
        await kit.service.update_global("financeiro", global_draft(transport="stdio", endpoint=None))
    assert caught.value.field == "transport"


@pytest.mark.us1
async def test_entrada_do_arquivo_e_global_e_somente_leitura() -> None:
    """US1 cen. 3: o `stdio` do arquivo aparece no registry como global e somente leitura."""
    kit = build(config=arquivo(do_arquivo()))

    (servidor,) = await kit.service.globals()
    assert (servidor.alias, servidor.transport, servidor.origin) == ("arquivos", "stdio", "file")
    assert servidor.read_only and servidor.command == STDIO_CMD and servidor.endpoint is None
    with pytest.raises(McpConflict):
        await kit.service.update_global("arquivos", global_draft(alias="arquivos"))
    with pytest.raises(McpConflict):
        await kit.service.delete_global("arquivos")
    with pytest.raises(McpConflict):
        await kit.service.create_global(global_draft(alias="arquivos"))


@pytest.mark.us1
async def test_entrada_do_arquivo_com_erro_aparece_indisponivel() -> None:
    kit = build(config=arquivo(ConfigEntry(alias="ruim", problem="campo policy: obrigatório")))
    (servidor,) = await kit.service.globals()
    assert not servidor.available and servidor.reason is not None and "policy" in servidor.reason


@pytest.mark.us1
async def test_registro_armazenado_sombreado_pelo_arquivo() -> None:
    """R3: o operador passou a declarar no arquivo um alias que o armazenamento já tinha — o arquivo prevalece."""
    first = build()
    await first.service.create_global(global_draft(alias="arquivos"))
    kit = build(config=arquivo(do_arquivo()), store=first.store)

    servidores = await kit.service.globals()
    assert [(s.origin, s.available) for s in servidores] == [("file", True), ("registry", False)]
    sombreado = servidores[1]
    assert sombreado.reason is not None and "arquivo do operador" in sombreado.reason


@pytest.mark.us1
async def test_check_lista_anunciadas_e_faltantes_e_ignora_o_cache() -> None:
    kit = build()
    await kit.service.create_global(global_draft(policy=policy(allowed_tools=("saldo", "sumiu"), write_tools=())))

    saude = await kit.service.check("financeiro")
    assert saude.ok and saude.detail is None
    assert saude.tools == tuple(tool.name for tool in TOOLS)
    assert saude.missing == ("sumiu",)
    await kit.service.check("financeiro")
    assert operations(kit.transport).count("list_tools") == 2, "a saúde não usa o cache"


@pytest.mark.us1
async def test_check_de_servidor_fora_do_ar_e_desabilitado() -> None:
    kit = build(servers={FINANCEIRO_URL: scripted(failure="conexão recusada")})
    await kit.service.create_global(global_draft())
    saude = await kit.service.check("financeiro")
    assert not saude.ok and saude.detail == "conexão recusada"

    await kit.service.update_global("financeiro", global_draft(enabled=False))
    saude = await kit.service.check("financeiro")
    assert not saude.ok and saude.detail is not None and "desabilitado" in saude.detail
    with pytest.raises(McpNotFound):
        await kit.service.check("nao-existe")


# --- de usuário (T034, US4) -------------------------------------------------------------------------------------------


@pytest.mark.us4
async def test_crud_de_usuario() -> None:
    kit = build()
    criado = await kit.service.create_mine(ANA, user_draft())
    assert (criado.alias, criado.scope, criado.owner) == ("~drive", "user", "user:ana")
    assert [s.alias for s in await kit.service.mine(ANA)] == ["~drive"]
    assert (await kit.service.get_mine(ANA, "~drive")).endpoint == DRIVE_URL
    alterado = await kit.service.update_mine(ANA, "~drive", user_draft(description="meus arquivos"))
    assert alterado.description == "meus arquivos"
    await kit.service.delete_mine(ANA, "~drive")
    assert await kit.service.mine(ANA) == []


@pytest.mark.us4
async def test_usuario_nao_registra_stdio_nem_credencial() -> None:
    kit = build()
    for draft, field in (
        (user_draft(transport="stdio", endpoint=None), "transport"),
        (user_draft(credential_ref="financeiro_token"), "credential_ref"),
        (user_draft(alias="drive"), "alias"),
    ):
        with pytest.raises(McpRejected) as caught:
            await kit.service.create_mine(ANA, draft)
        assert caught.value.field == field


@pytest.mark.us4
async def test_available_mostra_os_seus_e_os_globais_liberados_sem_detalhes() -> None:
    kit = build()
    await kit.service.create_global(global_draft(user_access=True))
    await kit.service.create_global(global_draft(alias="interno", user_access=False))
    await kit.service.create_mine(ANA, user_draft())
    await kit.service.create_mine(BIA, user_draft(alias="~dela"))

    resumo = await kit.service.available(ANA)
    assert [(s.alias, s.scope, s.description) for s in resumo] == [
        ("financeiro", "global", "Saldos e extratos"),
        ("~drive", "user", None),
    ]
    assert not hasattr(resumo[0], "endpoint"), "endpoint, credencial e política de globais não aparecem"


@pytest.mark.us4
async def test_global_e_de_usuario_com_o_mesmo_nome_coexistem() -> None:
    """US4 cen. 5."""
    kit = build()
    await kit.service.create_global(global_draft(alias="drive"))
    await kit.service.create_mine(ANA, user_draft(alias="~drive"))
    assert [s.alias for s in await kit.service.globals()] == ["drive"]
    assert [s.alias for s in await kit.service.mine(ANA)] == ["~drive"]
