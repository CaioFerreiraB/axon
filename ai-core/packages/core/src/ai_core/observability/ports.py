"""Portas secundárias do trace (specs/009-core-observability-evaluation/contracts/ports.md).

Não são seams: são internas do módulo, e só a composition root (spec 011) escolhe o adapter de cada uma.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from ai_core.observability.api import TraceRecord


class TraceExporter(Protocol):
    """Escrita no backend de trace."""

    def export(self, record: TraceRecord) -> None:
        """Entrega um registro ao backend. PODE levantar — quem chama trata e nunca propaga (FR-011)."""
        ...


class TraceReader(Protocol):
    """Leitura do backend de trace. Opcional no perfil: um backend que só escreve não a fornece (research R5)."""

    def read(self, request_id: str) -> Sequence[TraceRecord]:
        """Registros da requisição, na ordem de emissão; vazio quando não há nenhum."""
        ...


class Clock(Protocol):
    """Tempo, por porta: `domain/` é puro e o serviço não lê o relógio do sistema (ADR-013)."""

    def now(self) -> datetime:
        """Instante atual, sempre com timezone."""
        ...
