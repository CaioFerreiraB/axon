"""Adapters da porta `Clock` (ADR-013): o relógio do processo e o programado.

O programado mora aqui, e não no testkit, porque é o adapter em memória que o princípio XIII exige e o relógio do
perfil de teste da composition root (011 US3).
"""

from __future__ import annotations

import time
from collections.abc import Sequence


class MonotonicClock:
    """Relógio do processo. Só mede intervalo; o instante de parede de cada registro é da 009."""

    def monotonic(self) -> float:
        return time.monotonic()


class ScriptedClock:
    """Devolve leituras programadas, repetindo a última quando a sequência acaba.

    Torna a duração no trace determinística: duas leituras por chamada, diferença conhecida.
    """

    def __init__(self, readings: Sequence[float]) -> None:
        if not readings:
            raise ValueError("o relógio programado precisa de ao menos uma leitura")
        self._readings = tuple(readings)
        self._index = 0

    def monotonic(self) -> float:
        reading = self._readings[min(self._index, len(self._readings) - 1)]
        self._index += 1
        return reading
