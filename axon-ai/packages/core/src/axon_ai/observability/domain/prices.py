"""Preços com vigência e custo calculado na consulta (ADR-034, research R31). Puro, em `Decimal`.

Preço vigente num dia = o de maior `effective_from` ≤ o dia. Custo = tokens de entrada vezes o preço de entrada, mais
tokens de saída vezes o preço de saída, por milhão, com 6 casas; arredondar é da apresentação. Um preço lançado depois
corrige o histórico, porque nada fica pré-calculado.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Final

from axon_ai.observability.api import PRICE_SCALE, InvalidPrice, Price, PriceState

MILLION: Final = Decimal(1_000_000)
QUANTUM: Final = Decimal(1).scaleb(-PRICE_SCALE)


def check_amount(field: str, value: Decimal) -> Decimal:
    if not value.is_finite() or value < 0:
        raise InvalidPrice(f"{field}: precisa ser um número não negativo", field=field)
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -PRICE_SCALE:
        raise InvalidPrice(f"{field}: no máximo {PRICE_SCALE} casas decimais", field=field)
    return value


def effective_price(prices: Iterable[Price], *, provider: str, model: str, day: date) -> Price | None:
    candidates = [p for p in prices if p.provider == provider and p.model == model and p.effective_from <= day]
    return max(candidates, key=lambda p: p.effective_from) if candidates else None


def cost(price: Price, *, input_tokens: int, output_tokens: int) -> Decimal:
    raw = (Decimal(input_tokens) * price.usd_per_mtok_in + Decimal(output_tokens) * price.usd_per_mtok_out) / MILLION
    return raw.quantize(QUANTUM)


def with_states(prices: Sequence[Price], *, today: date) -> tuple[Price, ...]:
    """`current` = o vigente hoje do modelo; `superseded` = os anteriores; `scheduled` = os que ainda não valem."""
    result: list[Price] = []
    for price in prices:
        state: PriceState
        if price.effective_from > today:
            state = "scheduled"
        else:
            current = effective_price(prices, provider=price.provider, model=price.model, day=today)
            state = (
                "current" if current is not None and current.effective_from == price.effective_from else "superseded"
            )
        result.append(dataclasses.replace(price, state=state))
    return tuple(sorted(result, key=lambda p: (p.provider, p.model, p.effective_from), reverse=False))
