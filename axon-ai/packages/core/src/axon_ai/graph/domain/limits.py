"""Contagem e limite do loop `agentic` — puros (FR-006, research R20).

Uma **iteração** é uma chamada ao controller. Depois de cada decisão, `after_decision` diz para onde o loop vai: é a
tabela "Limite" de contracts/agentic-flow.md, e as arestas do grafo só a leem. Sem esta função, o loop é ilimitado —
a aresta "limite atingido" do `design.md` não é opcional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

DEFAULT_MAX_ITERATIONS: Final = 3
"""Limite quando o Assistant não declara outro (clarificação 3 de 2026-10-01). Constante, não configuração: quem precisa
de mais declara no Assistant."""

ITERATION_LIMIT: Final = "IterationLimit"
"""`kind` do registro do corte pelo limite; a geração o lê para avisar o modelo (R54)."""

type DecisionKind = Literal["tool", "invalid", "answer", "failed", "view_image"]
"""`failed`: a chamada ao controller falhou (FR-006a). `view_image` conta como iteração, como `tool` (ADR-044)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Route:
    next: Literal["controller", "generate"]
    truncated: bool


def effective_limit(declared: int | None) -> int:
    return DEFAULT_MAX_ITERATIONS if declared is None else declared


def after_decision(kind: DecisionKind, iteration: int, limit: int) -> Route:
    """Para onde o loop vai depois da decisão da iteração `iteration` (contada a partir de 1).

    `tool`, `view_image` e `invalid` voltam ao controller enquanto houver iteração; na última, vão à geração com
    truncamento.
    `answer` e `failed` vão sempre à geração, sem truncamento — não houve corte, houve fim.
    """
    if kind in ("answer", "failed"):
        return Route(next="generate", truncated=False)
    if iteration >= limit:
        return Route(next="generate", truncated=True)
    return Route(next="controller", truncated=False)
