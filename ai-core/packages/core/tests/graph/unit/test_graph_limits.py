"""T033 — contagem e limite do loop (`domain/limits.py`, R20): a tabela "Limite" do contracts/agentic-flow.md."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_core.graph.domain.limits import DEFAULT_MAX_ITERATIONS, DecisionKind, Route, after_decision, effective_limit

pytestmark = pytest.mark.us2


def test_limite_padrao_e_3() -> None:
    assert DEFAULT_MAX_ITERATIONS == 3
    assert effective_limit(None) == 3
    assert effective_limit(5) == 5
    assert effective_limit(1) == 1


@pytest.mark.parametrize(
    ("kind", "iteration", "limit", "route"),
    [
        ("tool", 1, 3, Route(next="controller", truncated=False)),
        ("tool", 3, 3, Route(next="generate", truncated=True)),
        ("invalid", 2, 3, Route(next="controller", truncated=False)),
        ("invalid", 3, 3, Route(next="generate", truncated=True)),
        ("answer", 1, 3, Route(next="generate", truncated=False)),
        ("answer", 3, 3, Route(next="generate", truncated=False)),
        ("failed", 1, 3, Route(next="generate", truncated=False)),
        ("failed", 3, 3, Route(next="generate", truncated=False)),
        ("tool", 1, 1, Route(next="generate", truncated=True)),
    ],
)
def test_tabela_de_rotas(kind: DecisionKind, iteration: int, limit: int, route: Route) -> None:
    assert after_decision(kind, iteration, limit) == route


@given(
    st.lists(st.sampled_from(["tool", "invalid", "answer", "failed"]), min_size=7, max_size=12),
    st.integers(min_value=1, max_value=6),
)
def test_a_simulacao_pura_nunca_passa_do_limite(kinds: list[DecisionKind], limit: int) -> None:
    calls = 0
    for kind in kinds:
        calls += 1
        if after_decision(kind, calls, limit).next == "generate":
            break
    assert calls <= limit
