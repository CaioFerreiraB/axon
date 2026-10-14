"""T055 — preços com vigência (R31): o vigente num dia, estados e validação."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from trace_testkit import AT

from ai_core.observability.api import InvalidPrice, Price
from ai_core.observability.domain.prices import check_amount, cost, effective_price, with_states

pytestmark = pytest.mark.us5


def _price(since: date, inp: str = "1") -> Price:
    return Price(
        provider="openrouter",
        model="m",
        usd_per_mtok_in=Decimal(inp),
        usd_per_mtok_out=Decimal("2"),
        effective_from=since,
        created_by="user:root",
        created_at=AT,
    )


def test_vigente_pelo_maior_inicio_ate_o_dia() -> None:
    prices = [_price(date(2026, 1, 1), "1"), _price(date(2026, 6, 1), "3")]
    assert effective_price(prices, provider="openrouter", model="m", day=date(2026, 5, 31)) == prices[0]
    assert effective_price(prices, provider="openrouter", model="m", day=date(2026, 6, 1)) == prices[1]
    assert effective_price(prices, provider="openrouter", model="m", day=date(2025, 12, 31)) is None
    assert effective_price(prices, provider="openrouter", model="outro", day=date(2026, 6, 1)) is None


def test_custo_em_decimal_com_seis_casas() -> None:
    assert cost(_price(date(2026, 1, 1), "0.15"), input_tokens=1234, output_tokens=56) == Decimal("0.000297")


def test_estados() -> None:
    prices = [_price(date(2026, 1, 1)), _price(date(2026, 9, 1)), _price(date(2026, 12, 1))]
    states = [p.state for p in with_states(prices, today=date(2026, 10, 14))]
    assert states == ["superseded", "current", "scheduled"]


@pytest.mark.parametrize("value", ["-1", "0.1234567", "NaN"])
def test_valor_invalido(value: str) -> None:
    with pytest.raises(InvalidPrice) as caught:
        check_amount("input", Decimal(value))
    assert caught.value.field == "input"
