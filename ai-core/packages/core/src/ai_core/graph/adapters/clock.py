"""Adapters da porta `Clock` (ADR-013): o relógio do processo e o fixo.

O fixo mora aqui, e não no testkit, porque é o adapter em memória que o princípio XIII exige e o relógio do perfil de
teste da composition root (011 US3 cenário 2).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime


class SystemClock:
    """Relógio do processo."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class FixedClock:
    """Data de referência fixa e leituras de cronômetro programadas, repetindo a última.

    É o que torna `reference_time` e a duração no trace verificáveis — e o conjunto dourado da 105 reproduzível.
    """

    def __init__(self, at: datetime, readings: Sequence[float] = (0.0, 1.0)) -> None:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("o relógio fixo precisa de uma data com timezone")
        if not readings:
            raise ValueError("o relógio fixo precisa de ao menos uma leitura de cronômetro")
        self._at = at
        self._readings = tuple(readings)
        self._index = 0

    def now(self) -> datetime:
        return self._at

    def monotonic(self) -> float:
        reading = self._readings[min(self._index, len(self._readings) - 1)]
        self._index += 1
        return reading
