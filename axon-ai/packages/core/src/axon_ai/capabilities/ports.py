"""Portas secundárias da 004 (specs/004-core-capability-gateway/contracts/ports.md e audit.md).

O cliente MCP e o Trace Sink não são portas daqui: chegam pelos seams da 007 e da 009, já montados pela composition
root. Nenhum tipo de biblioteca de infraestrutura aparece neste arquivo.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from axon_ai.capabilities.api import AuditEntry, AuditFilter, AuditRecord, AuditStatus
from axon_ai.capabilities.domain.records import PackTool
from axon_ai.observability.api import AttachmentInfo
from axon_ai.packs.api import Composition

__all__ = ["AuditLog", "Clock", "PackTool", "PackToolSource"]


class PackToolSource(Protocol):
    """A forma que a 004 exige da 002 (US3 cen. 1) até a passada dela — que a satisfaz estruturalmente."""

    def toolset(self, composition: Composition) -> Sequence[PackTool]:
        """Uma entrada por tool nativa e por retriever dos packs da composição, na ordem dela, com `<pack>.<tool>`."""
        ...


class AuditLog(Protocol):
    """Auditoria de tools de escrita, em dois passos: aberta antes do despacho e fechada depois (research R8)."""

    async def begin(self, entry: AuditEntry) -> str:
        """Grava o registro com `status="started"` e devolve o id."""
        ...

    async def finish(
        self,
        record_id: str,
        *,
        status: AuditStatus,
        result: str,
        at: datetime,
        attachments: Sequence[AttachmentInfo] = (),
    ) -> None: ...

    async def query(self, filter: AuditFilter) -> Sequence[AuditRecord]: ...


class Clock(Protocol):
    """Tempo (ADR-013): instante para a auditoria e cronômetro para a latência. A 011 injeta o relógio único."""

    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...
