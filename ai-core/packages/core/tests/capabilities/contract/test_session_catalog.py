"""T010 e T034 — o catálogo da sessão (contracts/capabilities-api.md, "Montagem do catálogo")."""

from __future__ import annotations

import pytest
from capabilities_testkit import Calls, FakeServer, build, context, grant, mcp_tool, native, retrieval

from ai_core.capabilities.api import CatalogConflict, ToolCall
from ai_core.observability.api import ExecutionError
from ai_core.observability.api import ToolCall as ToolCallEvent


def instalados(calls: Calls) -> list[object]:
    return [
        native("alfa", "ecoar", calls),
        retrieval("alfa", "buscar", calls, collections=("docs_alfa",)),
        native("beta", "ecoar", calls),
    ]


def servidores() -> dict[str, FakeServer]:
    return {
        "financeiro": FakeServer(tools=[mcp_tool("saldo"), mcp_tool("extrato")]),
        "drive": FakeServer(tools=[mcp_tool("ler")]),
    }


# --- US1 --------------------------------------------------------------------------------------------------------------


@pytest.mark.us1
async def test_so_o_pack_do_grant_com_prefixo() -> None:
    """US1 cen. 1."""
    calls = Calls()
    kit = build(tools=instalados(calls), servers=servidores(), calls=calls)
    session = await kit.service.open(grant(packs=["alfa"]), context())
    assert list(session.tools) == ["alfa.ecoar"], "o retriever precisa das coleções no grant (US5)"


@pytest.mark.us1
async def test_dois_grants_dois_catalogos_exatos() -> None:
    """Independent Test da US1: os mesmos packs e MCPs instalados, catálogos diferentes e exatos."""
    calls = Calls()
    kit = build(tools=instalados(calls), servers=servidores(), calls=calls)
    um = await kit.service.open(grant(packs=["alfa"], mcp=["financeiro"], collections=["docs_alfa"]), context())
    outro = await kit.service.open(grant(packs=["beta"], mcp=["drive"]), context())

    assert list(um.tools) == ["alfa.ecoar", "alfa.buscar", "financeiro.saldo", "financeiro.extrato"]
    assert list(outro.tools) == ["beta.ecoar", "drive.ler"]


@pytest.mark.us1
async def test_mcp_com_namespace_do_alias_e_so_o_que_o_servidor_libera() -> None:
    """US1 cen. 2: a allowlist do servidor é aplicada pela 007 — o catálogo traz o que a descoberta devolveu."""
    kit = build(servers={"financeiro": FakeServer(tools=[mcp_tool("saldo")])})
    session = await kit.service.open(grant(mcp=["financeiro"]), context())
    assert list(session.tools) == ["financeiro.saldo"]
    assert session.tools["financeiro.saldo"].kind == "mcp"


@pytest.mark.us1
async def test_tools_sao_catalog_tool_sem_handler() -> None:
    calls = Calls()
    kit = build(tools=instalados(calls), calls=calls)
    session = await kit.service.open(grant(packs=["alfa"]), context())
    tool = session.tools["alfa.ecoar"]
    assert type(tool).__name__ == "CatalogTool" and not hasattr(tool, "handler")


@pytest.mark.us1
async def test_mcp_que_falha_fica_em_unavailable_e_no_trace_e_os_outros_atendem() -> None:
    """Edge Cases: não silencioso e não derruba a execução."""
    servers = servidores() | {"caido": FakeServer(failure="conexão recusada")}
    kit = build(servers=servers)
    session = await kit.service.open(grant(mcp=["financeiro", "caido", "sumido"]), context())

    assert set(session.tools) == {"financeiro.saldo", "financeiro.extrato"}
    assert dict(session.unavailable) == {"caido": "conexão recusada", "sumido": "servidor desconhecido: sumido"}
    erros = kit.trace.of_type(ExecutionError)
    assert {(e.stage, e.kind) for e in erros} == {("catalog", "mcp_unavailable")}
    assert len(erros) == 2 and all(e.request_id == "req-1" for e in erros)


@pytest.mark.us1
async def test_descoberta_uma_vez_por_alias() -> None:
    kit = build(servers=servidores())
    await kit.service.open(grant(mcp=["financeiro", "drive"]), context())
    assert sorted(kit.mcp.discovered) == ["drive", "financeiro"]


@pytest.mark.us1
async def test_pack_e_alias_com_o_mesmo_nome_falham_a_montagem() -> None:
    calls = Calls()
    kit = build(tools=instalados(calls), servers={"alfa": FakeServer(tools=[mcp_tool("x")])}, calls=calls)
    with pytest.raises(CatalogConflict):
        await kit.service.open(grant(packs=["alfa"], mcp=["alfa"]), context())


@pytest.mark.us1
async def test_fora_do_catalogo_e_tool_inexistente_igual_para_proibida_e_inexistente() -> None:
    """US1 cen. 3, FR-005."""
    calls = Calls()
    kit = build(tools=instalados(calls), servers=servidores(), calls=calls)
    session = await kit.service.open(grant(packs=["alfa"], allowed=["alfa.ecoar"]), context())

    proibida = await session.execute(ToolCall(name="beta.ecoar", arguments={"texto": "x"}))
    inexistente = await session.execute(ToolCall(name="nunca.existiu", arguments={}))
    for resultado, nome in ((proibida, "beta.ecoar"), (inexistente, "nunca.existiu")):
        assert resultado.status == "unknown" and resultado.kind is None
        assert resultado.error == f"tool inexistente: {nome}"
    assert proibida.text.replace("beta.ecoar", "X") == inexistente.text.replace("nunca.existiu", "X")
    assert calls.total == 0
    eventos = kit.trace.of_type(ToolCallEvent)
    esperado = [("beta.ecoar", "unknown", None), ("nunca.existiu", "unknown", None)]
    assert [(e.tool, e.status, e.kind) for e in eventos] == esperado


# --- US5 --------------------------------------------------------------------------------------------------------------


@pytest.mark.us5
async def test_retriever_com_colecao_fora_do_grant_ausente_e_chamada_e_inexistente() -> None:
    """US5 cen. 1."""
    calls = Calls()
    beta = retrieval("alfa", "beta", calls, collections=("docs_beta",))
    kit = build(tools=[beta], calls=calls)
    session = await kit.service.open(grant(packs=["alfa"], collections=["docs_alfa"]), context())

    assert "alfa.beta" not in session.tools
    resultado = await session.execute(ToolCall(name="alfa.beta", arguments={"query": "x"}))
    assert resultado.status == "unknown" and calls.retrieval == []
    (evento,) = kit.trace.of_type(ToolCallEvent)
    assert (evento.tool, evento.status) == ("alfa.beta", "unknown")


@pytest.mark.us5
async def test_parcial_nao_basta_e_com_todas_aparece_como_recuperacao() -> None:
    """US5 cen. 2."""
    calls = Calls()
    ambas = retrieval("alfa", "ambas", calls, collections=("docs_alfa", "docs_beta"))
    kit = build(tools=[ambas], calls=calls)

    parcial = await kit.service.open(grant(packs=["alfa"], collections=["docs_alfa"]), context())
    assert "alfa.ambas" not in parcial.tools
    completo = await kit.service.open(grant(packs=["alfa"], collections=["docs_alfa", "docs_beta"]), context())
    tool = completo.tools["alfa.ambas"]
    assert tool.kind == "retrieval" and tool.parameters["required"] == ("query",)
