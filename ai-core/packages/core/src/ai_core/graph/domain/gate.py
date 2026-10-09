"""Portão de cobertura e junção por pack do `rag_first` — puros (FR-007, FR-007a; research R37 a R40).

O motor recupera pelo gateway, reordena cada pack com o reranker dele e decide aqui, sem modelo: coberto = há trechos e
(sem limiar ou melhor score ≥ limiar). Sem limiar por default, só a ausência de resultado escala — o número é do
operador e a 105 o calibra (princípio X). O score é o `Chunk.score` que o retriever do pack entregou.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from ai_core.capabilities.api import CatalogTool
from ai_core_contracts import Chunk

type GateRoute = Literal["generate", "controller", "fallback"]
"""`generate`: gerar com os trechos; `controller`: escalar para o loop; `fallback`: gerar sem trechos."""

RETRIEVAL_KIND = "retrieval"


@dataclass(frozen=True, slots=True, kw_only=True)
class Passage:
    """Um trecho recuperado, com o pack e a tool de recuperação de onde veio."""

    pack: str
    tool: str
    chunk: Chunk


@dataclass(frozen=True, slots=True, kw_only=True)
class RerankRefused:
    """O reranker devolveu o que o contrato 001 não permite; vale a ordem do retriever (R38)."""

    reason: str


def retrieval_tools(tools: Iterable[CatalogTool]) -> tuple[CatalogTool, ...]:
    """As tools de recuperação do catálogo, na ordem dele (packs na ordem do grant)."""
    return tuple(tool for tool in tools if tool.kind == RETRIEVAL_KIND)


def pack_of(name: str) -> str:
    """O pack de uma tool de pack: o prefixo antes do primeiro `.` (`<pack>.<nome>`, 002 FR-007)."""
    return name.split(".", 1)[0]


def first(passages: Sequence[Passage], n: int) -> tuple[Passage, ...]:
    return tuple(passages[:n])


def group_by_pack(passages: Iterable[Passage]) -> dict[str, tuple[Passage, ...]]:
    """Por pack, na ordem em que cada pack aparece; dentro do pack, a ordem recebida."""
    groups: dict[str, list[Passage]] = {}
    for item in passages:
        groups.setdefault(item.pack, []).append(item)
    return {pack: tuple(items) for pack, items in groups.items()}


def by_tool(passages: Iterable[Passage]) -> dict[str, tuple[Chunk, ...]]:
    """Os chunks por tool de recuperação, na ordem em que cada tool aparece — um passo sintético por tool (R41)."""
    groups: dict[str, list[Chunk]] = {}
    for item in passages:
        groups.setdefault(item.tool, []).append(item.chunk)
    return {name: tuple(chunks) for name, chunks in groups.items()}


def accept_reranked(
    documents: Sequence[Passage], reranked: Sequence[Chunk], *, top_k: int
) -> tuple[Passage, ...] | RerankRefused:
    """A ordem do reranker sobre os trechos **da recuperação**.

    O reranker decide a ordem; o trecho que segue é o que o retriever entregou, encontrado pelo `chunk_id` (princípio
    IX: o que chega ao modelo é o que a recuperação devolveu). Trecho estranho, repetido ou além de `top_k` é recusado.
    """
    known: dict[str, Passage] = {}
    for item in documents:
        known.setdefault(item.chunk.chunk_id, item)
    if len(reranked) > top_k:
        return RerankRefused(reason=f"devolveu {len(reranked)} trechos, mais de {top_k}")
    accepted: list[Passage] = []
    seen: set[str] = set()
    for chunk in reranked:
        if chunk.chunk_id not in known:
            return RerankRefused(reason=f"devolveu o trecho {chunk.chunk_id!r}, que não veio da recuperação")
        if chunk.chunk_id in seen:
            return RerankRefused(reason=f"devolveu o trecho {chunk.chunk_id!r} repetido")
        seen.add(chunk.chunk_id)
        accepted.append(known[chunk.chunk_id])
    return tuple(accepted)


def merge(groups: Sequence[Sequence[Passage]], passages: int) -> tuple[Passage, ...]:
    """Um pack só: a ordem do reranker dele, cortada. Vários: junção pelas cabeças dos grupos — a cada passo, a de maior
    score (empate: o grupo que vem antes) — cortada em `passages`.

    A ordem **dentro** de cada pack é a do reranker dele e não muda: no scouting, por exemplo, ela vem da fusão, e o
    score é a similaridade densa; reordenar o grupo por score desfaria o rerank (R38).
    """
    queues = [list(group) for group in groups if group]
    merged: list[Passage] = []
    while queues and len(merged) < passages:
        best = max(range(len(queues)), key=lambda index: (queues[index][0].chunk.score, -index))
        merged.append(queues[best].pop(0))
        if not queues[best]:
            queues.pop(best)
    return tuple(merged)


def best_score(passages: Sequence[Passage]) -> float | None:
    return max((item.chunk.score for item in passages), default=None)


def is_covered(passages: Sequence[Passage], min_score: float | None) -> bool:
    """Coberto = há trechos e (sem limiar ou melhor score ≥ limiar)."""
    best = best_score(passages)
    if best is None:
        return False
    return min_score is None or best >= min_score


def gate_route(covered: bool, *, escalate: bool) -> GateRoute:
    """Sem cobertura, escala só se o Assistant tem `controller` e há tool para o loop (FR-007a, R40)."""
    if covered:
        return "generate"
    return "controller" if escalate else "fallback"
