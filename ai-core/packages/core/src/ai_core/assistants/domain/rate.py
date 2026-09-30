"""Orçamento por (Principal, Assistant): janela deslizante (research R9)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

RATE_WINDOW: Final = timedelta(seconds=60)
"""`rpm` é por janela deslizante de 60 s (research R9)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RateDecision:
    """Concedido, ou recusado com quanto falta para a próxima concessão."""

    allowed: bool
    retry_after: timedelta | None = None


def sliding_window(
    instants: Sequence[datetime], *, now: datetime, limit: int, window: timedelta
) -> tuple[RateDecision, tuple[datetime, ...]]:
    """No máximo `limit` concessões em qualquer janela de `window` (US7 cen. 1).

    Devolve a decisão e os instantes a guardar: os que ainda estão na janela, mais `now` se concedido. Recusa não
    registra instante — insistir não prolonga a espera. `retry_after` é quanto falta para o mais antigo sair.
    """
    kept = tuple(instant for instant in instants if instant > now - window)
    if len(kept) < limit:
        return RateDecision(allowed=True), (*kept, now)
    return RateDecision(allowed=False, retry_after=min(kept) + window - now), kept
