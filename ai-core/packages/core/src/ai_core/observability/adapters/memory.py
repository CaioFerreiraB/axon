"""Adapters em memória do trace (spec 009): backend de teste e relógio fixo.

Todo porta secundária tem adapter em memória (princípio XIII); estes também servem ao perfil de teste da 011 (US3).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime

from ai_core.observability.api import ConnectionCheck, Price, TraceRecord, UsageGrouping, UsageOrigin
from ai_core.observability.domain.usage import aggregate
from ai_core.observability.ports import (
    DestinationSettings,
    DestinationStats,
    ExecutionRow,
    LangfuseCredentials,
    ModelCallRow,
    UsageAggregate,
)


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


# --- Fase 9 (contracts/ports.md, "Fase 9") ----------------------------------------------------------------------------


class RecordingDestination:
    """Destino que só guarda o que recebe — para provar o fan-out e onde o conteúdo vai (SC-007)."""

    def __init__(self, name: str = "gravador", *, accepts_content: bool = False) -> None:
        self._name = name
        self._accepts_content = accepts_content
        self.records: list[TraceRecord] = []
        self.flushes = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def accepts_content(self) -> bool:
        return self._accepts_content

    def export(self, record: TraceRecord) -> None:
        self.records.append(record)

    async def flush(self) -> None:
        self.flushes += 1

    def stats(self) -> DestinationStats:
        return DestinationStats(queued=0)


class FailingDestination(RecordingDestination):
    """Destino que levanta em todo `export`: a falha precisa ficar nele (R28)."""

    def export(self, record: TraceRecord) -> None:
        raise ConnectionError("destino fora do ar")


class InMemoryUsageStore:
    """Linhas em listas, com a mesma agregação do SQL (`domain/usage.py`)."""

    def __init__(self) -> None:
        self.calls: list[ModelCallRow] = []
        self.executions: dict[str, ExecutionRow] = {}

    async def append(self, calls: Sequence[ModelCallRow], executions: Sequence[ExecutionRow]) -> None:
        self.calls.extend(calls)
        for row in executions:
            self.executions[row.request_id] = row

    async def daily(
        self, *, start: datetime, end: datetime, tz: str, by: UsageGrouping, origin: UsageOrigin
    ) -> UsageAggregate:
        return aggregate(self.calls, start=start, end=end, tz=tz, by=by, origin=origin)

    async def purge(self, *, before: datetime) -> int:
        kept = [row for row in self.calls if row.at >= before]
        removed = len(self.calls) - len(kept)
        self.calls = kept
        old = [key for key, row in self.executions.items() if row.started_at < before]
        for key in old:
            del self.executions[key]
        return removed + len(old)


class InMemoryPriceStore:
    def __init__(self) -> None:
        self._prices: dict[tuple[str, str, date], Price] = {}

    async def all(self) -> Sequence[Price]:
        return sorted(self._prices.values(), key=lambda p: (p.provider, p.model, p.effective_from))

    async def add(self, price: Price) -> Price:
        self._prices[(price.provider, price.model, price.effective_from)] = price
        return price


class InMemoryDestinationSettingsStore:
    def __init__(self) -> None:
        self._settings = DestinationSettings()

    async def get(self) -> DestinationSettings:
        return self._settings

    async def put(self, settings: DestinationSettings, *, expected_version: int) -> bool:
        if self._settings.version != expected_version:
            return False
        self._settings = settings
        return True


class RecordingLangfuseTransport:
    """Transporte do Langfuse que só guarda o que receberia, com a resposta do "testar conexão" programável."""

    def __init__(self, *, check: ConnectionCheck | None = None) -> None:
        self.sent: list[TraceRecord] = []
        self.credentials: LangfuseCredentials | None = None
        self.reconfigured = 0
        self.checked: list[LangfuseCredentials] = []
        self._check = check or ConnectionCheck(ok=True, detail="projeto de teste")

    def send(self, record: TraceRecord) -> None:
        if self.credentials is not None:
            self.sent.append(record)

    async def check(self, credentials: LangfuseCredentials) -> ConnectionCheck:
        self.checked.append(credentials)
        return self._check

    def reconfigure(self, credentials: LangfuseCredentials | None) -> None:
        self.reconfigured += 1
        self.credentials = credentials

    async def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        self.credentials = None
