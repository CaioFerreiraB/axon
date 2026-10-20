"""Adapters em memória da 004: auditoria e tools de pack (contracts/ports.md).

Moram na distribuição, como os das outras specs: o perfil de teste da composition root os usa, e a suíte de um pack
externo monta a plataforma com eles.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime

from axon_ai.capabilities.api import AuditEntry, AuditFilter, AuditRecord, AuditStatus
from axon_ai.capabilities.ports import PackTool
from axon_ai.packs.api import Composition


class InMemoryAuditLog:
    """Registros numa lista; `id` sequencial."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    async def begin(self, entry: AuditEntry) -> str:
        record_id = str(len(self._records) + 1)
        self._records.append(
            AuditRecord(
                id=record_id,
                request_id=entry.request_id,
                principal=entry.principal,
                assistant=entry.assistant,
                tool=entry.tool,
                kind=entry.kind,
                arguments=entry.arguments,
                status="started",
                result=None,
                started_at=entry.started_at,
                finished_at=None,
            )
        )
        return record_id

    async def finish(self, record_id: str, *, status: AuditStatus, result: str, at: datetime) -> None:
        for index, record in enumerate(self._records):
            if record.id == record_id:
                self._records[index] = dataclasses.replace(record, status=status, result=result, finished_at=at)
                return
        raise LookupError(f"registro de auditoria '{record_id}' não existe")

    async def query(self, filter: AuditFilter) -> Sequence[AuditRecord]:
        matching = [record for record in self._records if _matches(record, filter)]
        matching.sort(key=lambda record: (record.started_at, int(record.id)), reverse=True)
        return matching[: filter.limit]


def _matches(record: AuditRecord, filter: AuditFilter) -> bool:
    return (
        (filter.principal is None or record.principal == filter.principal)
        and (filter.assistant is None or record.assistant == filter.assistant)
        and (filter.tool is None or record.tool == filter.tool)
        and (filter.since is None or record.started_at >= filter.since)
        and (filter.until is None or record.started_at <= filter.until)
    )


class StaticPackTools:
    """Tools de pack dadas — o `PackToolSource` das suítes até a 002 expor o dela."""

    def __init__(self, tools: Sequence[PackTool] = ()) -> None:
        self._tools = tuple(tools)

    def toolset(self, composition: Composition) -> Sequence[PackTool]:
        by_pack = {pack: [tool for tool in self._tools if tool.pack == pack] for pack in composition.packs}
        return [tool for pack in composition.packs for tool in by_pack[pack]]
