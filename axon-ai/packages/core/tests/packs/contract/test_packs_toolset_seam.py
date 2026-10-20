"""T038 — o seam Pack Toolset (contracts/pack-runtime-api.md; US3 cenário 1; FR-007; research R18, R19)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from packs_testkit import load_runtime, make_pack_class

from axon_ai.packs.api import CompositionError, PackToolset
from axon_ai.packs.ports import PackSettings
from axon_ai_contracts import (
    RETRIEVAL_TOOL_PARAMETERS,
    Chunk,
    JSONValue,
    NamedRetriever,
    PackContext,
    ToolInvocation,
    ToolSpec,
)


async def _handler(invocation: ToolInvocation) -> object:
    return dict(invocation.arguments)


class _Retriever:
    async def search(
        self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None
    ) -> list[Chunk]:
        return []


def tool(name: str) -> ToolSpec:
    return ToolSpec(
        name=name, description=f"tool {name}", parameters={"type": "object"}, kind="native", handler=_handler
    )


def pack(name: str, *tool_names: str, retrievers: tuple[tuple[str, tuple[str, ...]], ...] = ()) -> Any:
    def tools(self: Any, ctx: PackContext) -> tuple[ToolSpec, ...]:
        return tuple(tool(t) for t in tool_names)

    def retrievers_hook(self: Any, ctx: PackContext) -> tuple[NamedRetriever, ...]:
        return tuple(
            NamedRetriever(name=r, description=f"busca {r}", collections=frozenset(cols), retriever=_Retriever())
            for r, cols in retrievers
        )

    return make_pack_class(name, tools=tools, retrievers=retrievers_hook)


def runtime(*packs: Any, disabled: tuple[str, ...] = ()) -> Any:
    settings = {p.name: PackSettings(enabled=p.name not in disabled) for p in packs}
    return load_runtime(*packs, settings=settings)


def test_packs_com_a_mesma_tool_local_ficam_separados_por_namespace() -> None:
    """US3 cenário 1."""
    loaded = runtime(pack("a", "search"), pack("b", "search"))
    composition = loaded.compose(["a", "b"])
    assert [item.name for item in loaded.toolset(composition)] == ["a.search", "b.search"]


def test_ordem_da_composicao_e_nativas_antes_dos_retrievers() -> None:
    loaded = runtime(pack("a", "um", "dois", retrievers=(("busca", ("docs",)),)), pack("b", "tres"))
    items = loaded.toolset(loaded.compose(["b", "a"]))
    assert [item.name for item in items] == ["b.tres", "a.um", "a.dois", "a.busca"]
    assert [item.pack for item in items] == ["b", "a", "a", "a"]


def test_spec_tem_o_nome_local() -> None:
    loaded = runtime(pack("a", "search"))
    (item,) = loaded.toolset(loaded.compose(["a"]))
    assert item.spec.name == "search" and item.spec.kind == "native" and item.retriever is None


def test_retriever_vira_tool_de_recuperacao_com_as_colecoes() -> None:
    loaded = runtime(pack("a", retrievers=(("busca", ("docs_a", "docs_b")),)))
    (item,) = loaded.toolset(loaded.compose(["a"]))
    assert item.name == "a.busca" and item.spec.kind == "retrieval" and not item.spec.mutates
    assert item.spec.parameters == RETRIEVAL_TOOL_PARAMETERS
    assert item.retriever is not None and item.retriever.collections == frozenset({"docs_a", "docs_b"})


def test_pack_fora_da_composicao_nao_aparece_e_composicao_vazia_e_vazia() -> None:
    loaded = runtime(pack("a", "x"), pack("b", "y"))
    assert [item.name for item in loaded.toolset(loaded.compose(["b"]))] == ["b.y"]
    assert list(loaded.toolset(loaded.compose([]))) == []


def test_composicao_com_pack_em_erro_e_recusada() -> None:
    """A composição recebida é revalidada (R10): montada à mão com um pack desabilitado, é recusada."""
    from axon_ai.packs.api import Composition

    loaded = runtime(pack("a", "x"), pack("b", "y"), disabled=("b",))
    with pytest.raises(CompositionError):
        loaded.toolset(Composition(packs=("a", "b")))


def test_o_runtime_cumpre_o_protocol() -> None:
    toolset: PackToolset = runtime(pack("a", "x"))
    assert toolset is not None
