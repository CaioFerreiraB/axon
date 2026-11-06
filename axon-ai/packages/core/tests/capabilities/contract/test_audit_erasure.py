"""T046 — pseudônimo na auditoria (incremento 9.7, US7; FR-019, FR-020, SC-006; research R16)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from capabilities_testkit import T0, build

from axon_ai.assistants.api import RequestRejected
from axon_ai.capabilities.api import AuditEntry, AuditErasure, AuditErasureReport, AuditFilter

pytestmark = pytest.mark.us7

PSEUDO = "deleted:0123456789abcdef"


def entry(n: int, principal: str = "user:ana") -> AuditEntry:
    return AuditEntry(
        request_id=f"req-{n}",
        principal=principal,
        assistant="geral",
        tool="alfa.pagar",
        kind="native",
        arguments={"conta": "1"},
        started_at=T0 + timedelta(minutes=n),
    )


async def _registros(audit: Any) -> None:
    for n in (1, 2, 3):
        await audit.begin(entry(n))
    await audit.begin(entry(4, "user:bia"))


async def test_cenarios_1_e_2_troca_e_repete() -> None:
    kit = build()
    await _registros(kit.audit)
    erasure: AuditErasure = kit.service

    assert await erasure.erase_subject("user:ana", pseudonym=PSEUDO) == AuditErasureReport(audit_records=3)
    registros = await kit.service.records(AuditFilter())
    assert sorted(r.principal for r in registros) == [PSEUDO, PSEUDO, PSEUDO, "user:bia"]
    assert await kit.service.erase_subject("user:ana", pseudonym=PSEUDO) == AuditErasureReport(audit_records=0)


@pytest.mark.parametrize(
    ("subject", "pseudonym", "field"),
    [
        ("", PSEUDO, "subject"),
        ("ana", PSEUDO, "subject"),
        (PSEUDO, "deleted:fedcba9876543210", "subject"),
        ("user:ana", "deleted:XYZ", "pseudonym"),
        ("user:ana", "user:outra", "pseudonym"),
        ("user:ana", "deleted:0123456789ABCDEF", "pseudonym"),
    ],
)
async def test_cenario_3_formatos_recusados_sem_tocar_a_auditoria(subject: str, pseudonym: str, field: str) -> None:
    kit = build()
    await _registros(kit.audit)
    antes = await kit.service.records(AuditFilter())

    with pytest.raises(RequestRejected) as erro:
        await kit.service.erase_subject(subject, pseudonym=pseudonym)

    assert erro.value.field == field
    assert await kit.service.records(AuditFilter()) == antes


async def test_sc_006_nenhuma_linha_com_o_subject(pg_pool: Any) -> None:
    from axon_ai.capabilities.adapters.audit_postgres import PostgresAuditLog

    kit = build(audit=PostgresAuditLog(pg_pool))
    await _registros(kit.audit)

    assert await kit.service.erase_subject("user:ana", pseudonym=PSEUDO) == AuditErasureReport(audit_records=3)
    async with pg_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT count(*) FILTER (WHERE principal = 'user:ana'), count(*) FROM capabilities.audit"
        )
        assert await cursor.fetchone() == (0, 4)
