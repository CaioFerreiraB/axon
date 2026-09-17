"""Adapters em memória do trace (spec 009): backend de teste e relógio fixo.

Todo porta secundária tem adapter em memória (princípio XIII); estes também servem ao perfil de teste da 011 (US3).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from ai_core.observability.api import TraceRecord


class InMemoryTraceBackend:
    """Escreve e lê em memória, preservando a ordem de emissão por requisição."""

    def __init__(self) -> None:
        self._records: defaultdict[str, list[TraceRecord]] = defaultdict(list)

    def export(self, record: TraceRecord) -> None:
        self._records[record.request_id].append(record)

    def read(self, request_id: str) -> tuple[TraceRecord, ...]:
        return tuple(self._records.get(request_id, ()))


class FixedClock:
    """Relógio fixo: torna o trace determinístico em teste e permite fixar a data no perfil de teste (011 US3)."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("instant precisa ter timezone")
        self._instant = instant

    def now(self) -> datetime:
        return self._instant
