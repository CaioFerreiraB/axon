"""T027 — conformidade da porta `AuditLog` (contracts/audit.md): memória e Postgres (ADR-015)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from capabilities_testkit import T0

from axon_ai.capabilities.api import AuditEntry, AuditFilter

pytestmark = pytest.mark.us4


def entry(n: int = 0, **overrides: Any) -> AuditEntry:
    base: dict[str, Any] = {
        "request_id": f"req-{n}",
        "principal": "user:ana",
        "assistant": "geral",
        "tool": "alfa.pagar",
        "kind": "native",
        "arguments": {"conta": "1", "valor": 10.5, "itens": [1, 2], "nested": {"a": None}},
        "started_at": T0 + timedelta(minutes=n),
    }
    return AuditEntry(**(base | overrides))


async def test_begin_abre_started_sem_resultado(audit_log: Any) -> None:
    record_id = await audit_log.begin(entry())
    (record,) = await audit_log.query(AuditFilter())
    assert record.id == record_id and record.status == "started"
    assert record.result is None and record.finished_at is None
    identidade = (record.principal, record.assistant, record.tool, record.kind)
    assert identidade == ("user:ana", "geral", "alfa.pagar", "native")
    assert dict(record.arguments) == {"conta": "1", "valor": 10.5, "itens": [1, 2], "nested": {"a": None}}
    assert record.started_at == T0


async def test_finish_grava_status_resultado_e_instante(audit_log: Any) -> None:
    record_id = await audit_log.begin(entry())
    resultado = "<tool_result …>pago</tool_result>"
    await audit_log.finish(record_id, status="ok", result=resultado, at=T0 + timedelta(seconds=2))
    (record,) = await audit_log.query(AuditFilter())
    assert record.status == "ok" and record.result == "<tool_result …>pago</tool_result>"
    assert record.finished_at == T0 + timedelta(seconds=2)


async def test_filtros_ordem_e_limite(audit_log: Any) -> None:
    await audit_log.begin(entry(1))
    await audit_log.begin(entry(2, principal="user:bia"))
    await audit_log.begin(entry(3, assistant="outro"))
    await audit_log.begin(entry(4, tool="fin.transferir", kind="mcp"))

    assert [r.request_id for r in await audit_log.query(AuditFilter())] == ["req-4", "req-3", "req-2", "req-1"]
    assert [r.request_id for r in await audit_log.query(AuditFilter(principal="user:bia"))] == ["req-2"]
    assert [r.request_id for r in await audit_log.query(AuditFilter(assistant="outro"))] == ["req-3"]
    assert [r.request_id for r in await audit_log.query(AuditFilter(tool="fin.transferir"))] == ["req-4"]
    periodo = AuditFilter(since=T0 + timedelta(minutes=2), until=T0 + timedelta(minutes=3))
    assert [r.request_id for r in await audit_log.query(periodo)] == ["req-3", "req-2"]
    assert [r.request_id for r in await audit_log.query(AuditFilter(limit=2))] == ["req-4", "req-3"]


async def test_dois_registros_para_duas_chamadas_iguais(audit_log: Any) -> None:
    first = await audit_log.begin(entry())
    second = await audit_log.begin(entry())
    assert first != second and len(await audit_log.query(AuditFilter())) == 2


async def test_finish_grava_o_resumo_das_imagens_sem_bytes(audit_log: Any) -> None:
    """R13, FR-017: id, tipo e tamanho; sem imagens, a lista vazia."""
    from axon_ai.observability.api import AttachmentInfo

    com, sem = await audit_log.begin(entry(1)), await audit_log.begin(entry(2))
    info = AttachmentInfo(id="img-0123456789ab", mime="image/png", size_bytes=2048)
    await audit_log.finish(com, status="ok", result="r", at=T0, attachments=(info,))
    await audit_log.finish(sem, status="ok", result="r", at=T0)
    records = {record.id: record for record in await audit_log.query(AuditFilter())}
    assert records[com].attachments == (info,)
    assert records[sem].attachments == ()
