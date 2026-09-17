"""Serviço de trace: implementa os seams Trace Sink e Trace (spec 009, contracts/trace-api.md).

Orquestra `domain/` e as portas. Falha de backend nunca chega a quem emite: é contada e registrada (FR-011).
"""

from __future__ import annotations

import logging
from typing import Final

from ai_core.observability.api import Trace, TraceEvent, TraceQueryUnavailable
from ai_core.observability.domain.records import to_record
from ai_core.observability.ports import Clock, TraceExporter, TraceReader

logger: Final = logging.getLogger("ai_core.observability")


class TraceService:
    """Um serviço por processo, montado pela composition root (spec 011) com os adapters do perfil."""

    def __init__(self, *, exporter: TraceExporter, reader: TraceReader | None, clock: Clock) -> None:
        self._exporter = exporter
        self._reader = reader
        self._clock = clock
        self._dropped = 0

    def emit(self, event: TraceEvent) -> None:
        """Registra um dado de trace. Nunca levanta: trace é observação, não o trabalho (FR-011)."""
        record = to_record(event, self._clock.now())
        try:
            self._exporter.export(record)
        except Exception as error:
            self._dropped += 1
            logger.warning(
                "evento de trace descartado (%s: %s); requisição %s, tipo %s",
                type(error).__name__,
                error,
                record.request_id,
                record.type,
            )

    def trace(self, request_id: str) -> Trace:
        """Eventos da requisição, na ordem de emissão."""
        if self._reader is None:
            raise TraceQueryUnavailable(
                f"o backend configurado ({type(self._exporter).__name__}) não oferece consulta de trace"
            )
        return Trace(request_id=request_id, records=tuple(self._reader.read(request_id)))

    def dropped_events(self) -> int:
        """Eventos perdidos por falha do backend desde o início do processo; a saúde agregada (011 US5) lê isto."""
        return self._dropped
