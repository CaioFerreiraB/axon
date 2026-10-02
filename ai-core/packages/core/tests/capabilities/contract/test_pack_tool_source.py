"""Conformidade da porta `PackToolSource` (contracts/ports.md), contra `StaticPackTools` e contra o `PackRuntime` da
002, que a satisfaz estruturalmente (002 research R20)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from capabilities_testkit import Calls, native, retrieval

from ai_core.capabilities.adapters.memory import StaticPackTools
from ai_core.capabilities.ports import PackToolSource
from ai_core.packs.api import Composition

pytestmark = pytest.mark.us1


def static_source() -> PackToolSource:
    calls = Calls()
    return StaticPackTools(
        [
            native("alfa", "ecoar", calls),
            retrieval("alfa", "buscar", calls, collections=("docs_alfa",)),
            native("beta", "ecoar", calls),
            native("gama", "outra", calls),
        ]
    )


def runtime_source() -> PackToolSource:
    """O `PackRuntime` da 002 com packs equivalentes — a mesma suíte prova as duas implementações (002 R20)."""
    from packs_testkit import load_runtime, make_pack_class

    def build(name: str, *tools: str, retrievers: tuple[tuple[str, tuple[str, ...]], ...] = ()) -> type:
        calls = Calls()

        def tools_hook(self: object, ctx: object) -> tuple[object, ...]:
            return tuple(native(name, tool, calls).spec for tool in tools)

        def retrievers_hook(self: object, ctx: object) -> tuple[object, ...]:
            return tuple(
                retrieval(name, r, calls, collections=cols).retriever for r, cols in retrievers
            )

        return make_pack_class(name, tools=tools_hook, retrievers=retrievers_hook)

    from ai_core.packs.ports import PackSettings

    packs = [
        build("alfa", "ecoar", retrievers=(("buscar", ("docs_alfa",)),)),
        build("beta", "ecoar"),
        build("gama", "outra"),
    ]
    settings = {pack.name: PackSettings(enabled=True) for pack in packs}  # type: ignore[attr-defined]
    runtime: PackToolSource = load_runtime(*packs, settings=settings)  # type: ignore[assignment]
    return runtime


SOURCES = pytest.mark.parametrize("source", [static_source, runtime_source], ids=["memoria", "pack-runtime"])


@SOURCES
def test_so_os_packs_da_composicao_na_ordem_dela(source: Callable[[], PackToolSource]) -> None:
    tools = source().toolset(Composition(packs=("beta", "alfa")))
    assert [tool.name for tool in tools] == ["beta.ecoar", "alfa.ecoar", "alfa.buscar"]


@SOURCES
def test_nome_com_namespace_e_spec_com_o_nome_local(source: Callable[[], PackToolSource]) -> None:
    tools = {tool.name: tool for tool in source().toolset(Composition(packs=("alfa",)))}
    assert tools["alfa.ecoar"].pack == "alfa" and tools["alfa.ecoar"].spec.name == "ecoar"
    assert tools["alfa.ecoar"].spec.kind == "native" and tools["alfa.ecoar"].retriever is None


@SOURCES
def test_retriever_com_kind_retrieval_e_as_colecoes(source: Callable[[], PackToolSource]) -> None:
    (buscar,) = [tool for tool in source().toolset(Composition(packs=("alfa",))) if tool.name == "alfa.buscar"]
    assert buscar.spec.kind == "retrieval" and buscar.retriever is not None
    assert buscar.retriever.collections == frozenset({"docs_alfa"})


@SOURCES
def test_composicao_vazia(source: Callable[[], PackToolSource]) -> None:
    assert list(source().toolset(Composition(packs=()))) == []
