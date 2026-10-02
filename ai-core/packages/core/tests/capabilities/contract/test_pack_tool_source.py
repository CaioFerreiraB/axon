"""Conformidade da porta `PackToolSource` (contracts/ports.md): contra `StaticPackTools` agora; a passada da 002 roda
a mesma suíte contra o `PackRuntime`."""

from __future__ import annotations

import pytest
from capabilities_testkit import Calls, native, retrieval

from ai_core.capabilities.adapters.memory import StaticPackTools
from ai_core.capabilities.ports import PackToolSource
from ai_core.packs.api import Composition

pytestmark = pytest.mark.us1


def source() -> PackToolSource:
    calls = Calls()
    return StaticPackTools(
        [
            native("alfa", "ecoar", calls),
            retrieval("alfa", "buscar", calls, collections=("docs_alfa",)),
            native("beta", "ecoar", calls),
            native("gama", "outra", calls),
        ]
    )


def test_so_os_packs_da_composicao_na_ordem_dela() -> None:
    tools = source().toolset(Composition(packs=("beta", "alfa")))
    assert [tool.name for tool in tools] == ["beta.ecoar", "alfa.ecoar", "alfa.buscar"]


def test_nome_com_namespace_e_spec_com_o_nome_local() -> None:
    tools = {tool.name: tool for tool in source().toolset(Composition(packs=("alfa",)))}
    assert tools["alfa.ecoar"].pack == "alfa" and tools["alfa.ecoar"].spec.name == "ecoar"
    assert tools["alfa.ecoar"].spec.kind == "native" and tools["alfa.ecoar"].retriever is None


def test_retriever_com_kind_retrieval_e_as_colecoes() -> None:
    (buscar,) = [tool for tool in source().toolset(Composition(packs=("alfa",))) if tool.name == "alfa.buscar"]
    assert buscar.spec.kind == "retrieval" and buscar.retriever is not None
    assert buscar.retriever.collections == frozenset({"docs_alfa"})


def test_composicao_vazia() -> None:
    assert list(source().toolset(Composition(packs=()))) == []
