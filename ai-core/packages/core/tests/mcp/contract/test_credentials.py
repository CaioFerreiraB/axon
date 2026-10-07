"""T023 — credencial por referência, resolvida no momento da operação (US2; FR-003, FR-004; research R7)."""

from __future__ import annotations

import pytest
from mcp_testkit import FINANCEIRO_URL, build, global_draft, grant, scripted

from ai_core.mcp.domain.records import StdioCommand
from ai_core.mcp.ports import ConfigEntry, McpConfig

pytestmark = pytest.mark.us2

SEGREDO = "s3cr3t-valor-do-token"


def bearer() -> object:
    return global_draft(auth_type="bearer", credential_ref="financeiro_token")


async def test_bearer_chega_ao_transporte_no_cabecalho() -> None:
    """US2 cen. 2: a credencial é obtida no servidor, no momento da chamada."""
    kit = build(secrets={"financeiro_token": SEGREDO})
    await kit.service.create_global(bearer())
    client = kit.service.client_for(grant("financeiro"))

    await client.discover(["financeiro"])
    await client.execute("financeiro", "saldo", {})

    for _operation, target in kit.transport.calls:
        assert target.headers["Authorization"] == f"Bearer {SEGREDO}"
        assert SEGREDO not in repr(target)


async def test_sem_autenticacao_nao_ha_cabecalho() -> None:
    kit = build()
    await kit.service.create_global(global_draft())
    await kit.service.client_for(grant("financeiro")).discover(["financeiro"])
    ((_operation, target),) = kit.transport.calls
    assert "Authorization" not in target.headers


async def test_stdio_recebe_os_segredos_no_ambiente() -> None:
    entrada = ConfigEntry(
        alias="arquivos",
        draft=global_draft(alias="arquivos", transport="stdio", endpoint=None),
        stdio=StdioCommand(command="/bin/mcp", secrets={"TOKEN": "arquivos_token"}),
    )
    kit = build(config=McpConfig(entries=(entrada,)), secrets={"arquivos_token": SEGREDO})
    kit.transport.add("/bin/mcp", scripted())
    await kit.service.client_for(grant("arquivos")).discover(["arquivos"])
    ((_operation, target),) = kit.transport.calls
    assert dict(target.environment) == {"TOKEN": SEGREDO}


async def test_referencia_sem_valor_falha_nomeando_a_referencia() -> None:
    """Edge case: erro explícito na chamada e no health check — nomeando a referência, nunca um valor."""
    kit = build()
    await kit.service.create_global(bearer())
    client = kit.service.client_for(grant("financeiro"))

    descoberta = await client.discover(["financeiro"])
    assert descoberta.unavailable["financeiro"] == "credencial 'financeiro_token' não configurada"
    resultado = await client.execute("financeiro", "saldo", {})
    assert resultado.error == "credencial 'financeiro_token' não configurada"
    saude = await kit.service.check("financeiro")
    assert not saude.ok and saude.detail == "credencial 'financeiro_token' não configurada"
    assert kit.transport.calls == [], "sem credencial, nada sai do processo"


async def test_nenhum_valor_devolvido_contem_o_segredo() -> None:
    kit = build(
        secrets={"financeiro_token": SEGREDO},
        servers={FINANCEIRO_URL: scripted(failure=f"falhou com Authorization: Bearer {SEGREDO}")},
    )
    criado = await kit.service.create_global(bearer())
    client = kit.service.client_for(grant("financeiro"))
    devolvidos = [
        criado,
        await kit.service.get_global("financeiro"),
        await kit.service.check("financeiro"),
        await client.discover(["financeiro"]),
        await client.execute("financeiro", "saldo", {}),
        *await kit.service.globals(),
    ]
    for valor in devolvidos:
        assert SEGREDO not in repr(valor), "mesmo que o adapter repita o cabeçalho na falha, o serviço apaga o segredo"
    assert criado.credential_ref == "financeiro_token", "só o nome da referência"
