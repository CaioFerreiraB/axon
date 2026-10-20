"""`RateCounterStore` em memória, num processo único (design.md; research R9).

A decisão é a regra pura do domínio; aqui só se guardam os instantes por par. Sem `await` entre ler e gravar, a
operação é atômica no laço de eventos. Réplicas do serviço pediriam outro adapter — o `design.md` já prevê a troca.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from axon_ai.assistants.domain.rate import RateDecision, sliding_window


class InMemoryRateCounterStore:
    """Instantes concedidos por (subject, Assistant), podados a cada acesso."""

    def __init__(self) -> None:
        self._instants: dict[tuple[str, str], tuple[datetime, ...]] = {}

    async def acquire(self, key: tuple[str, str], *, now: datetime, limit: int, window: timedelta) -> RateDecision:
        decision, kept = sliding_window(self._instants.get(key, ()), now=now, limit=limit, window=window)
        self._instants[key] = kept
        return decision
