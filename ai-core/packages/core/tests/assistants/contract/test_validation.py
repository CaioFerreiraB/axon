"""T013 / T041 — validação de referências (FR-011): um estado por Assistant, com motivos que nomeiam campo e
referência."""

from __future__ import annotations

import pytest
from assistants_testkit import FakePackRegistry, assistant, assistants_service, config, pack_entry, private

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


# --- Fase 3 (T057; US8 cen. 2 a 4; research R19 a R22) -------------------------------------------------------------

FLOW_ROLES = {"chat": ("generation",), "agentic": ("controller", "generation")}
AGENTIC_MODELS = {"generation": "ollama/qwen3:1.7b", "controller": "ollama/qwen3:1.7b", "allow": ["ollama/*"]}


def _com_tools() -> FakePackRegistry:
    """`generic` oferece a tool `calculate`; `rag` prefere `agentic` (o flow efetivo vem dele)."""
    return FakePackRegistry(pack_entry("generic", tools=("calculate",)), pack_entry("rag", preferred_flow="agentic"))


@pytest.mark.us8
async def test_us8_regras_da_fase_3_deixam_indisponivel_nomeando_o_motivo() -> None:
    service = assistants_service(
        config(
            {
                "sem-controller": assistant(flow="agentic"),
                "herda-agentic": assistant(packs=["rag"]),
                "sem-namespace": assistant(allowed_tools=["calculate"]),
                "fora": private(write_tools=["outro.x"]),
                "colisao": assistant(mcp=["generic"]),
                "ok": assistant(flow="agentic", models=AGENTIC_MODELS, allowed_tools=["generic.calculate"]),
            }
        ),
        packs=_com_tools(),
        flow_roles=FLOW_ROLES,
        mcp=InMemoryMcpDirectory(global_aliases={"generic"}),
    )
    statuses = {status.name: status for status in (await service.validate()).statuses}

    papel = "models: o flow 'agentic' exige o papel 'controller', que o Assistant não declara"
    assert papel in statuses["sem-controller"].reasons
    assert papel in statuses["herda-agentic"].reasons
    assert any(r.startswith("allowed_tools: 'calculate'") for r in statuses["sem-namespace"].reasons)
    assert any(r.startswith("write_tools: 'outro.x'") for r in statuses["fora"].reasons)
    assert any(r.startswith("mcp: o alias 'generic' colide") for r in statuses["colisao"].reasons)
    assert statuses["ok"].available, statuses["ok"].reasons


@pytest.mark.us8
async def test_us8_o_exemplo_completo_do_contrato_e_valido() -> None:
    interno = private(
        allow=["user:caio", "group:operadores"],
        flow="agentic",
        mcp=["financeiro"],
        allowed_tools=["generic.calculate", "financeiro.saldo", "financeiro.transferir"],
        write_tools=["financeiro.transferir"],
        models=AGENTIC_MODELS,
    )
    service = assistants_service(
        config({"interno": interno}),
        packs=_com_tools(),
        flow_roles=FLOW_ROLES,
        mcp=InMemoryMcpDirectory(global_aliases={"financeiro"}),
    )
    (status,) = (await service.validate()).statuses
    assert status.available, status.reasons
