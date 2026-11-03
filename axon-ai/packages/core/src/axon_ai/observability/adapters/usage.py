"""`UsageDestination`: o trace vira linhas de uso, gravadas em lote fora do caminho de quem emite (ADR-034; R30).

`export` só projeta e enfileira (buffer limitado: cheio, a linha mais antiga sai e é contada). `flush` — chamado por uma
tarefa periódica da 011 e no encerramento — grava o lote pelo `UsageStore`; falha de gravação é contada aqui e nunca
chega a quem emite. A origem (`production` ou `evaluation`) é do processo: a 011 a fixa (clarificação de 2026-10-13).

Com um estimador de impacto (ADR-056; research R46), o `flush` estima cada chamada elegível antes de gravar: sem par,
a linha leva a marca de tentada; uma estimativa que levanta é contada, e a linha grava sem impacto.
"""

from __future__ import annotations

import dataclasses
import logging
from collections import deque
from datetime import datetime
from typing import Final

from axon_ai.observability.api import TraceRecord
from axon_ai.observability.domain.usage import EXECUTION_TTL, call_row, execution_finished, execution_started
from axon_ai.observability.domain.usage_records import eligible
from axon_ai.observability.ports import (
    Clock,
    DestinationStats,
    ExecutionRow,
    ImpactEstimator,
    ModelCallRow,
    Origin,
    UsageStore,
)

logger: Final = logging.getLogger("axon_ai.observability")

BUFFER: Final = 10_000


class UsageDestination:
    def __init__(
        self,
        *,
        store: UsageStore,
        origin: Origin,
        clock: Clock,
        buffer: int = BUFFER,
        estimator: ImpactEstimator | None = None,
    ) -> None:
        self._store = store
        self._estimator = estimator
        self._impact_failed = 0
        self._origin: Origin = origin
        self._clock = clock
        self._buffer: deque[ModelCallRow | ExecutionRow] = deque(maxlen=buffer)
        self._open: dict[str, ExecutionRow] = {}
        self._dropped_at: deque[datetime] = deque(maxlen=1_000)
        self._dropped = 0
        self._last_error: str | None = None
        self._last_sent_at: datetime | None = None

    @property
    def name(self) -> str:
        return "usage"

    @property
    def accepts_content(self) -> bool:
        return False

    def export(self, record: TraceRecord) -> None:
        if record.type == "execution_started":
            row = execution_started(record, origin=self._origin)
            self._open[record.request_id] = row
            self._push(row)
        elif record.type == "model_call":
            opened = self._open.get(record.request_id)
            self._push(call_row(record, assistant=opened.assistant if opened else None, origin=self._origin))
        elif record.type == "execution_finished":
            opened = self._open.pop(record.request_id, None)
            if opened is not None:
                self._push(execution_finished(opened, record))
        self._expire(record.at)

    def _push(self, row: ModelCallRow | ExecutionRow) -> None:
        if len(self._buffer) == self._buffer.maxlen:
            self._dropped += 1
            self._dropped_at.append(self._clock.now())
        self._buffer.append(row)

    def _expire(self, now: datetime) -> None:
        """Execução aberta há mais de 1 h não espera mais as chamadas dela (R30)."""
        stale = [rid for rid, row in self._open.items() if now - row.started_at > EXECUTION_TTL]
        for rid in stale:
            del self._open[rid]

    async def flush(self, store: UsageStore | None = None) -> None:
        """Grava o lote. `store` troca o armazenamento só desta gravação: a 011 passa o da sessão da linha de comando,
        em que o pool de serviço não abre (R13 da 011)."""
        if not self._buffer:
            return
        batch = list(self._buffer)
        self._buffer.clear()
        calls = [self._estimate(row) for row in batch if isinstance(row, ModelCallRow)]
        executions = [row for row in batch if isinstance(row, ExecutionRow)]
        try:
            await (store or self._store).append(calls, executions)
        except Exception as error:
            self._dropped += len(batch)
            self._dropped_at.extend([self._clock.now()] * min(len(batch), 1_000))
            self._last_error = f"{type(error).__name__}: {error}"[:300]
            logger.warning("uso: %s linhas descartadas (%s)", len(batch), type(error).__name__)
            return
        self._last_sent_at = self._clock.now()

    def _estimate(self, row: ModelCallRow) -> ModelCallRow:
        if self._estimator is None or not eligible(row):
            return row
        try:
            impact = self._estimator.estimate(row.provider, row.model, row.output_tokens, row.duration_ms / 1000)
        except Exception as error:
            self._impact_failed += 1
            logger.warning("impacto: estimativa falhou para %s/%s (%s)", row.provider, row.model, type(error).__name__)
            return row
        return dataclasses.replace(row, impact=impact, impact_tried=True)

    def stats(self) -> DestinationStats:
        return DestinationStats(
            impact_failed=self._impact_failed,
            queued=len(self._buffer),
            dropped=self._dropped,
            dropped_at=tuple(self._dropped_at),
            last_error=self._last_error,
            last_sent_at=self._last_sent_at,
        )
