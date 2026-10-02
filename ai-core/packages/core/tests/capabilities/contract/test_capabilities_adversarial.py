"""T024 — SC-001: nenhuma execução invoca tool fora do seu catálogo, para qualquer nome pedido."""

from __future__ import annotations

import asyncio

import pytest
from capabilities_testkit import EMPTY_SCHEMA, Calls, FakeServer, build, context, grant, mcp_tool, native, retrieval
from hypothesis import given, settings
from hypothesis import strategies as st

from ai_core.capabilities.api import ToolCall

pytestmark = pytest.mark.us3

CATALOGO = {"alfa.ecoar", "fin.saldo"}

PERTO = [
    "alfa.ecoar ", " alfa.ecoar", "ALFA.ecoar", "alfa.Ecoar", "alfa..ecoar", "alfa.ecoar\x00", "alfa.\u0435coar",
    "alfa.oculta", "alfa.buscar", "alfa.pagar", "fin.saldo\n", "fin.transferir", "~fin.saldo", "beta.ecoar",
    "ecoar", "saldo", "alfa", "fin", "", ".", "alfa.ecoar.extra", "fin/saldo", "fin:saldo",
]


def nomes() -> st.SearchStrategy[str]:
    prefixos = st.sampled_from(["alfa.", "fin.", "beta.", "~fin.", "~alfa.", ""])
    return st.one_of(
        st.sampled_from(PERTO),
        st.text(max_size=40),
        st.builds(lambda p, s: p + s, prefixos, st.text(max_size=20)),
    )


def montar() -> tuple[object, Calls]:
    calls = Calls()
    tools = [
        native("alfa", "ecoar", calls, parameters=EMPTY_SCHEMA),
        native("alfa", "oculta", calls, parameters=EMPTY_SCHEMA),
        native("alfa", "pagar", calls, mutates=True, parameters=EMPTY_SCHEMA),
        retrieval("alfa", "buscar", calls, collections=("restrita",)),
        native("beta", "ecoar", calls, parameters=EMPTY_SCHEMA),
    ]
    saldo = mcp_tool("saldo", parameters=EMPTY_SCHEMA)
    servers = {"fin": FakeServer(tools=[saldo, mcp_tool("transferir", mutates=True)])}
    kit = build(tools=tools, servers=servers, calls=calls)
    return kit, calls


@settings(max_examples=300, deadline=None)
@given(nome=nomes())
def test_nenhum_nome_fora_do_catalogo_executa(nome: str) -> None:
    kit, calls = montar()

    async def run() -> str:
        session = await kit.service.open(  # type: ignore[attr-defined]
            grant(packs=["alfa"], mcp=["fin"], allowed=["alfa.ecoar", "fin.saldo", "fin.transferir"]), context()
        )
        assert set(session.tools) == CATALOGO
        return str((await session.execute(ToolCall(name=nome, arguments={}))).status)

    status = asyncio.run(run())
    if nome in CATALOGO:
        assert status == "ok"
    else:
        assert status == "unknown"
        assert calls.total == 0, f"executou fora do catálogo: {nome!r}"
