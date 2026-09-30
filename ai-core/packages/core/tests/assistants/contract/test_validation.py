"""T013 / T041 — validação de referências (FR-011): um estado por Assistant, com motivos que nomeiam campo e
referência."""

from __future__ import annotations

from assistants_testkit import assistant, assistants_service, config, private

from ai_core.assistants.adapters.memory import InMemoryCollectionCatalog, InMemoryMcpDirectory


async def test_us1_um_estado_por_assistant_de_sistema_em_ordem_de_nome() -> None:
    service = assistants_service(config({"zeta": assistant(), "alfa": private(), "meio": assistant()}))
    report = await service.validate()

    assert [status.name for status in report.statuses] == ["alfa", "meio", "zeta"]
    assert all(status.origin == "system" and status.available for status in report.statuses)
    assert report.ok


async def test_us1_referencias_pendentes_viram_motivos() -> None:
    service = assistants_service(
        config(
            {
                "flow": assistant(flow="inexistente"),
                "pack": assistant(packs=["financeiro"]),
                "mcp": assistant(mcp=["drive"]),
                "colecao": assistant(collections=["normas"]),
                "carga": assistant(visibility=None),
                "ok": assistant(),
            }
        ),
        mcp=InMemoryMcpDirectory(global_aliases={"finance"}),
        collections=InMemoryCollectionCatalog({"docs"}),
    )
    statuses = {status.name: status for status in (await service.validate()).statuses}

    assert statuses["ok"].available
    assert any(r.startswith("flow") and "inexistente" in r and "chat" in r for r in statuses["flow"].reasons)
    assert any(r.startswith("packs") and "financeiro" in r for r in statuses["pack"].reasons)
    assert any(r.startswith("mcp") and "drive" in r for r in statuses["mcp"].reasons)
    assert any(r.startswith("collections") and "normas" in r for r in statuses["colecao"].reasons)
    assert any("visibility" in r for r in statuses["carga"].reasons)


async def test_us1_catalogos_vazios_da_fase_deixam_mcp_e_colecao_indisponiveis() -> None:
    service = assistants_service(config({"m": assistant(mcp=["finance"]), "c": assistant(collections=["docs"])}))
    report = await service.validate()
    assert not report.ok
    assert all(not status.available for status in report.statuses)


async def test_us1_relatorio_com_um_indisponivel_nao_esta_ok() -> None:
    service = assistants_service(config({"a": assistant(), "b": assistant(packs=["financeiro"])}))
    report = await service.validate()
    assert not report.ok
    assert [s.available for s in report.statuses] == [True, False]


# --- US6: Assistants de usuário no relatório (R14) -------------------------------------------------------------------


async def test_validacao_inclui_os_assistants_de_usuario_com_o_dono() -> None:
    from assistants_testkit import T0, draft

    from ai_core.assistants.adapters.memory import InMemoryUserAssistantStore
    from ai_core.assistants.ports import StoredUserAssistant

    users = InMemoryUserAssistantStore()
    await users.insert(StoredUserAssistant(owner="user:ana", draft=draft(), created_at=T0, updated_at=T0))
    await users.insert(
        StoredUserAssistant(owner="user:bia", draft=draft("x", packs=("financeiro",)), created_at=T0, updated_at=T0)
    )
    await users.insert(
        StoredUserAssistant(owner="user:bia", draft=draft("y", mcp=("agenda",)), created_at=T0, updated_at=T0)
    )
    service = assistants_service(
        config({"geral": assistant()}),
        users=users,
        mcp=InMemoryMcpDirectory(by_owner={"user:ana": {"agenda"}}),
    )
    statuses = (await service.validate()).statuses

    assert [(s.name, s.origin, s.owner) for s in statuses] == [
        ("geral", "system", None),
        ("~meu-rag", "user", "user:ana"),
        ("~x", "user", "user:bia"),
        ("~y", "user", "user:bia"),
    ]
    assert [s.available for s in statuses] == [True, True, False, False]
    assert any("financeiro" in r for r in statuses[2].reasons)
    assert any(r.startswith("mcp") and "agenda" in r for r in statuses[3].reasons)
