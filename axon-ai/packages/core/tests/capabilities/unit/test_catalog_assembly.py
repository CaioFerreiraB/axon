"""T009 e T034 — a montagem do catálogo, pura (research R3; FR-001 a FR-003, FR-010, FR-012)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from capabilities_testkit import EMPTY_SCHEMA, Calls, mcp_tool, native, retrieval

from axon_ai.capabilities.api import CatalogConflict
from axon_ai.capabilities.domain.catalog import assemble
from axon_ai.capabilities.domain.records import PackTool
from axon_ai_contracts import ToolSpec

CALLS = Calls()
ALFA = [native("alfa", "search", CALLS), native("alfa", "ecoar", CALLS)]
BETA = [native("beta", "search", CALLS)]


def names(
    packs: Sequence[PackTool] = (),
    mcp: Sequence[tuple[str, Sequence[ToolSpec]]] = (),
    *,
    allowed: frozenset[str] | None = None,
    write: frozenset[str] = frozenset(),
    collections: frozenset[str] = frozenset(),
) -> list[str]:
    assembly = assemble(packs, mcp, allowed=allowed, write=write, collections=collections)
    return list(assembly.entries)


# --- US1 --------------------------------------------------------------------------------------------------------------


@pytest.mark.us1
def test_namespace_de_pack_e_de_mcp_na_ordem_de_montagem() -> None:
    mcp = [("financeiro", [mcp_tool("saldo")]), ("~drive", [mcp_tool("buscar")])]
    assert names(ALFA + BETA, mcp) == ["alfa.search", "alfa.ecoar", "beta.search", "financeiro.saldo", "~drive.buscar"]


@pytest.mark.us1
def test_allowed_tools_exato_com_namespace() -> None:
    """US1 cen. 4: `a.search` fica, `b.search` sai; `search` sem namespace não casa nada."""
    assert names(ALFA + BETA, allowed=frozenset({"alfa.search"})) == ["alfa.search"]
    assert names(ALFA + BETA, allowed=frozenset({"search"})) == []
    assert names(ALFA + BETA, allowed=frozenset({"ALFA.search", "alfa.search "})) == []


@pytest.mark.us1
def test_sem_allowed_tools_nao_ha_filtro() -> None:
    assert names(ALFA, allowed=None) == ["alfa.search", "alfa.ecoar"]


@pytest.mark.us1
def test_pack_e_alias_com_o_mesmo_nome_e_conflito() -> None:
    with pytest.raises(CatalogConflict) as caught:
        names(ALFA, [("alfa", [mcp_tool("outra")])])
    assert caught.value.name == "alfa"


@pytest.mark.us1
def test_nome_completo_repetido_e_conflito() -> None:
    with pytest.raises(CatalogConflict) as caught:
        names([native("alfa", "x", CALLS), native("alfa", "x", CALLS)])
    assert caught.value.name == "alfa.x"


@pytest.mark.us1
def test_esquema_invalido_sai_com_o_motivo() -> None:
    quebrada = native("alfa", "quebrada", CALLS, parameters={"type": 3})  # type: ignore[dict-item]
    assembly = assemble([quebrada, *ALFA], [], allowed=None, write=frozenset(), collections=frozenset())
    assert "alfa.quebrada" not in assembly.entries
    assert [name for name, _reason in assembly.invalid] == ["alfa.quebrada"]


@pytest.mark.us1
def test_entrada_expoe_catalog_tool_sem_handler_e_a_origem() -> None:
    assembly = assemble(ALFA, [("fin", [mcp_tool("saldo")])], allowed=None, write=frozenset(), collections=frozenset())
    tool = assembly.entries["alfa.ecoar"].tool
    assert (tool.name, tool.kind, tool.mutates) == ("alfa.ecoar", "native", False)
    assert not hasattr(tool, "handler")
    mcp = assembly.entries["fin.saldo"]
    assert (mcp.tool.kind, mcp.alias, mcp.local_name, mcp.trusted_schema) == ("mcp", "fin", "saldo", False)
    assert assembly.entries["alfa.ecoar"].trusted_schema


# --- escrita (usada pela US4) -----------------------------------------------------------------------------------------


@pytest.mark.us4
def test_escrita_so_com_write_tools_exato() -> None:
    pagar = native("alfa", "pagar", CALLS, mutates=True, parameters=EMPTY_SCHEMA)
    assert names([pagar]) == []
    assert names([pagar], write=frozenset({"pagar"})) == []
    assert names([pagar], write=frozenset({"alfa.pagar"})) == ["alfa.pagar"]
    assert names([], [("fin", [mcp_tool("transferir", mutates=True)])], write=frozenset({"fin.transferir"})) == [
        "fin.transferir"
    ]


# --- coleções (US5) ---------------------------------------------------------------------------------------------------


@pytest.mark.us5
def test_retriever_so_com_todas_as_colecoes_no_grant() -> None:
    beta = retrieval("alfa", "beta", CALLS, collections=("docs_beta",))
    ambas = retrieval("alfa", "ambas", CALLS, collections=("docs_alfa", "docs_beta"))
    alfa = retrieval("alfa", "so_alfa", CALLS, collections=("docs_alfa",))
    assert names([beta, ambas, alfa], collections=frozenset({"docs_alfa"})) == ["alfa.so_alfa"]
    assert names([beta, ambas, alfa], collections=frozenset({"docs_alfa", "docs_beta"})) == [
        "alfa.beta",
        "alfa.ambas",
        "alfa.so_alfa",
    ]
