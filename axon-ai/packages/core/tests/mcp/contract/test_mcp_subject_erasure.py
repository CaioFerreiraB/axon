"""T055 — apagar os servidores de um dono (incremento 9.7, US7; FR-018, FR-019, SC-005; research R18, R19)."""

from __future__ import annotations

from typing import Any

import pytest
from mcp_testkit import ANA, BIA, DRIVE_URL, build, global_draft, grant, user_draft

from axon_ai.assistants.api import Principal
from axon_ai.mcp.api import McpErasureReport, McpRejected, McpSubjectErasure
from axon_ai.mcp.domain.records import ConfigEntry, McpConfig, StdioCommand

pytestmark = pytest.mark.us7


def _arquivo() -> McpConfig:
    return McpConfig(
        entries=(
            ConfigEntry(
                alias="arquivos",
                draft=global_draft(alias="arquivos", transport="stdio", endpoint=None),
                stdio=StdioCommand(command="/bin/mcp"),
            ),
        )
    )


async def _cenario(store: Any = None) -> Any:
    kit = build(config=_arquivo(), store=store)
    await kit.service.create_global(global_draft())
    await kit.service.create_global(global_draft(alias="liberado", user_access=True))
    await kit.service.create_mine(ANA, user_draft())
    await kit.service.create_mine(ANA, user_draft(alias="~agenda"))
    await kit.service.create_mine(BIA, user_draft())
    return kit


async def test_cenario_1_apaga_os_do_dono_e_nada_mais() -> None:
    kit = await _cenario()
    erasure: McpSubjectErasure = kit.service

    report = await erasure.erase_subject("user:ana")

    assert report == McpErasureReport(servers=2)
    assert await kit.service.mine(ANA) == []
    assert await kit.service.aliases(owner="user:ana") == frozenset({"liberado"})
    assert [s.alias for s in await kit.service.mine(BIA)] == ["~drive"]
    assert sorted(s.alias for s in await kit.service.globals()) == ["arquivos", "financeiro", "liberado"]


async def test_cenario_2_repetir_devolve_zero() -> None:
    kit = await _cenario()
    await kit.service.erase_subject("user:ana")

    assert await kit.service.erase_subject("user:ana") == McpErasureReport(servers=0)
    assert [s.alias for s in await kit.service.mine(BIA)] == ["~drive"]


@pytest.mark.parametrize("subject", ["", "ana", "user:", "deleted:0123456789abcdef", "user: ana"])
async def test_cenario_3_subject_invalido_e_recusado_sem_tocar_nada(subject: str) -> None:
    kit = await _cenario()
    antes = await kit.store.all()

    with pytest.raises(McpRejected) as erro:
        await kit.service.erase_subject(subject)

    assert erro.value.field == "subject"
    assert await kit.store.all() == antes


async def test_cenario_4_o_cache_e_esquecido_e_o_alias_fica_livre() -> None:
    kit = await _cenario()
    cliente = kit.service.client_for(grant("~drive", assistant="~meu"))
    assert (await cliente.discover(["~drive"])).tools
    descobertas = [op for op, target in kit.transport.calls if op == "list_tools" and target.alias == "~drive"]
    assert len(descobertas) == 1

    await kit.service.erase_subject("user:ana")
    nova = Principal(subject="user:ana", scheme="oidc")
    recriado = await kit.service.create_mine(nova, user_draft())

    assert recriado.endpoint == DRIVE_URL
    assert (await kit.service.client_for(grant("~drive", assistant="~meu", principal=nova)).discover(["~drive"])).tools
    descobertas = [op for op, target in kit.transport.calls if op == "list_tools" and target.alias == "~drive"]
    assert len(descobertas) == 2, "a primeira descoberta do dono novo vai ao servidor"


async def test_o_cache_de_outros_donos_e_dos_globais_fica() -> None:
    kit = await _cenario()
    await kit.service.client_for(grant("~drive", assistant="~meu", principal=BIA)).discover(["~drive"])
    await kit.service.client_for(grant("financeiro")).discover(["financeiro"])
    antes = len(kit.transport.calls)

    await kit.service.erase_subject("user:ana")
    await kit.service.client_for(grant("~drive", assistant="~meu", principal=BIA)).discover(["~drive"])
    await kit.service.client_for(grant("financeiro")).discover(["financeiro"])

    assert len(kit.transport.calls) == antes, "as entradas de B e do global continuam no cache"


async def test_sc_005_nenhuma_linha_do_schema_mcp_cita_o_subject(pg_pool: Any) -> None:
    from axon_ai.mcp.adapters.registry_postgres import PostgresServerStore

    kit = await _cenario(PostgresServerStore(pg_pool))
    assert await kit.service.erase_subject("user:ana") == McpErasureReport(servers=2)

    async with pg_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'mcp' "
            "AND data_type IN ('text', 'jsonb', 'ARRAY')"
        )
        columns = await cursor.fetchall()
        achados = []
        for table, column in columns:
            cursor = await connection.execute(
                f"SELECT count(*) FROM mcp.{table} WHERE {column}::text LIKE %s", ("%user:ana%",)
            )
            (count,) = await cursor.fetchone()
            if count:
                achados.append((table, column, count))
        cursor = await connection.execute("SELECT count(*) FROM mcp.servers")
        (restantes,) = await cursor.fetchone()
    assert columns, "a varredura precisa achar colunas"
    assert achados == []
    assert restantes == 3, "os dois globais do armazenamento e o ~drive de B"
