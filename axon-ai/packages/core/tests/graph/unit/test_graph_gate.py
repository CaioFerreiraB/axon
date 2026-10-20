"""T066 — o portão de cobertura e a junção por pack do `rag_first` (`domain/gate.py`; research R37 a R40). Puro."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from axon_ai.capabilities.api import CatalogTool
from axon_ai.graph.domain.gate import (
    Passage,
    RerankRefused,
    accept_reranked,
    best_score,
    by_tool,
    first,
    gate_route,
    group_by_pack,
    is_covered,
    merge,
    pack_of,
    retrieval_tools,
)
from axon_ai_contracts import Chunk

pytestmark = pytest.mark.us3


def chunk(chunk_id: str, score: float = 0.5) -> Chunk:
    return Chunk(chunk_id=chunk_id, text=f"texto {chunk_id}", score=score, document="Doc")


def passage(chunk_id: str, score: float = 0.5, *, pack: str = "docs", tool: str = "docs.search") -> Passage:
    return Passage(pack=pack, tool=tool, chunk=chunk(chunk_id, score))


def tool(name: str, kind: str) -> CatalogTool:
    return CatalogTool(name=name, description="d", parameters={"type": "object"}, kind=kind)  # type: ignore[arg-type]


def test_tools_de_recuperacao_na_ordem_do_catalogo() -> None:
    tools = [tool("a.calc", "native"), tool("b.search", "retrieval"), tool("m.x", "mcp"), tool("a.search", "retrieval")]
    assert [t.name for t in retrieval_tools(tools)] == ["b.search", "a.search"]
    assert retrieval_tools([]) == ()


@pytest.mark.parametrize(("name", "pack"), [("docs.search", "docs"), ("a.b.c", "a"), ("solto", "solto")])
def test_pack_de_uma_tool(name: str, pack: str) -> None:
    assert pack_of(name) == pack


def test_primeiros() -> None:
    items = tuple(passage(f"c{n}") for n in range(4))
    assert first(items, 2) == items[:2] and first(items, 9) == items and first((), 3) == ()


def test_agrupa_por_pack_e_por_tool_na_ordem_de_aparicao() -> None:
    a1, b1, a2 = (
        passage("a1", pack="a", tool="a.s"),
        passage("b1", pack="b", tool="b.s"),
        passage("a2", pack="a", tool="a.t"),
    )
    assert group_by_pack([a1, b1, a2]) == {"a": (a1, a2), "b": (b1,)}
    assert list(group_by_pack([b1, a1])) == ["b", "a"]
    assert by_tool([a1, b1, a2]) == {"a.s": (a1.chunk,), "b.s": (b1.chunk,), "a.t": (a2.chunk,)}


def test_rerank_aceito_mantem_a_ordem_do_reranker_e_os_trechos_da_recuperacao() -> None:
    documentos = tuple(passage(f"c{n}", score=n / 10) for n in range(5))
    reordenado = [Chunk(chunk_id="c3", text="outro texto", score=0.99, document="X"), chunk("c0")]
    aceito = accept_reranked(documentos, reordenado, top_k=2)
    assert aceito == (documentos[3], documentos[0]), "o reranker decide a ordem; o trecho é o da recuperação"


@pytest.mark.parametrize(
    ("reordenado", "motivo"),
    [
        (["c1", "estranho"], "não veio da recuperação"),
        (["c1", "c1"], "repetido"),
        (["c0", "c1", "c2"], "mais de 2"),
    ],
)
def test_rerank_recusado(reordenado: list[str], motivo: str) -> None:
    documentos = tuple(passage(f"c{n}") for n in range(5))
    recusado = accept_reranked(documentos, [chunk(i) for i in reordenado], top_k=2)
    assert isinstance(recusado, RerankRefused) and motivo in recusado.reason


def test_juncao_de_um_grupo_so_corta() -> None:
    grupo = tuple(passage(f"c{n}", score=0.1 * n) for n in range(7))
    assert merge([grupo], 5) == grupo[:5], "um pack só: a ordem do reranker dele, sem reordenar por score"
    assert merge([], 5) == ()


def test_juncao_de_varios_grupos_por_score_estavel() -> None:
    a = (passage("a1", 0.9, pack="a"), passage("a2", 0.5, pack="a"))
    b = (passage("b1", 0.9, pack="b"), passage("b2", 0.7, pack="b"), passage("b3", 0.1, pack="b"))
    assert [p.chunk.chunk_id for p in merge([a, b], 4)] == ["a1", "b1", "b2", "a2"]


def test_juncao_nao_desfaz_a_ordem_do_reranker_dentro_do_pack() -> None:
    a = (passage("a1", 0.6, pack="a"), passage("a2", 0.95, pack="a"))
    b = (passage("b1", 0.8, pack="b"),)
    assert [p.chunk.chunk_id for p in merge([a, b], 3)] == ["b1", "a1", "a2"]


@pytest.mark.parametrize(
    ("scores", "min_score", "covered"),
    [
        ([], None, False),
        ([], 0.5, False),
        ([0.1], None, True),
        ([0.3, 0.8], 0.8, True),
        ([0.3, 0.79], 0.8, False),
        ([0.0], 0.0, True),
    ],
)
def test_cobertura(scores: list[float], min_score: float | None, covered: bool) -> None:
    items = tuple(passage(f"c{n}", s) for n, s in enumerate(scores))
    assert is_covered(items, min_score) is covered
    assert best_score(items) == (max(scores) if scores else None)


@pytest.mark.parametrize(
    ("covered", "escalate", "route"),
    [(True, True, "generate"), (True, False, "generate"), (False, True, "controller"), (False, False, "fallback")],
)
def test_rota_do_portao(covered: bool, escalate: bool, route: str) -> None:
    assert gate_route(covered, escalate=escalate) == route


@given(
    groups=st.lists(st.lists(st.floats(min_value=0, max_value=1, allow_nan=False), max_size=8), min_size=1, max_size=4),
    passages=st.integers(min_value=1, max_value=10),
)
def test_propriedade_da_juncao(groups: list[list[float]], passages: int) -> None:
    built = [
        tuple(passage(f"p{g}-{n}", score, pack=f"p{g}") for n, score in enumerate(scores))
        for g, scores in enumerate(groups)
    ]
    merged = merge(built, passages)
    assert len(merged) <= passages
    todos = [item for group in built for item in group]
    assert all(item in todos for item in merged)
    for group in built:
        posicoes = [group.index(item) for item in merged if item in group]
        assert posicoes == sorted(posicoes), "a ordem relativa de cada grupo é preservada"
