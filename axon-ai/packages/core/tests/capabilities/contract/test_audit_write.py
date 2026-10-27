"""T028 — a escrita auditada (contracts/audit.md, "A ordem"; FR-011; SC-002; US4 cen. 2)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import pytest
from capabilities_testkit import EMPTY_SCHEMA, Calls, FakeServer, build, context, grant, mcp_tool, native

from axon_ai.capabilities.adapters.memory import InMemoryAuditLog
from axon_ai.capabilities.api import AuditEntry, AuditFilter, AuditRecord, AuditStatus, GatewayLimits, ToolCall
from axon_ai.observability.api import AttachmentInfo

pytestmark = pytest.mark.us4

ARGS = {"conta": "1", "valor": 10}
SCHEMA = {"type": "object", "properties": {"conta": {"type": "string"}, "valor": {"type": "number"}}}


class SpyAudit(InMemoryAuditLog):
    """A memória, com falhas programáveis e o estado do registro no momento do despacho."""

    def __init__(self, *, fail_begin: bool = False, fail_finish: bool = False) -> None:
        super().__init__()
        self.fail_begin = fail_begin
        self.fail_finish = fail_finish

    async def begin(self, entry: AuditEntry) -> str:
        if self.fail_begin:
            raise ConnectionError("banco fora")
        return await super().begin(entry)

    async def finish(
        self,
        record_id: str,
        *,
        status: AuditStatus,
        result: str,
        at: datetime,
        attachments: Sequence[AttachmentInfo] = (),
    ) -> None:
        if self.fail_finish:
            raise ConnectionError("banco caiu no meio")
        await super().finish(record_id, status=status, result=result, at=at, attachments=attachments)


async def montar(audit: InMemoryAuditLog, **native_kwargs: Any) -> tuple[Any, Any, Calls, list[Sequence[AuditRecord]]]:
    calls = Calls()
    seen: list[Sequence[AuditRecord]] = []

    async def snapshot() -> None:
        seen.append(await audit.query(AuditFilter()))

    pagar = native(
        "alfa", "pagar", calls, mutates=True, parameters=SCHEMA, result="pago", before=snapshot, **native_kwargs
    )
    ler = native("alfa", "ler", calls, parameters=EMPTY_SCHEMA)
    kit = build(tools=[pagar, ler], calls=calls, audit=audit, limits=GatewayLimits(timeout_ms=1000))
    session = await kit.service.open(grant(packs=["alfa"], write=["alfa.pagar"]), context())
    return kit, session, calls, seen


async def test_escrita_gera_registro_completo_com_o_resultado_que_o_modelo_recebeu() -> None:
    audit = SpyAudit()
    _kit, session, _calls, _seen = await montar(audit)
    resultado = await session.execute(ToolCall(name="alfa.pagar", arguments=ARGS))

    (record,) = await audit.query(AuditFilter())
    identidade = (record.principal, record.assistant, record.tool, record.kind)
    assert identidade == ("user:ana", "geral", "alfa.pagar", "native")
    assert dict(record.arguments) == ARGS and record.request_id == "req-1"
    assert record.status == "ok" and record.result == resultado.text and record.finished_at is not None


async def test_o_registro_abre_antes_do_despacho() -> None:
    audit = SpyAudit()
    _kit, session, _calls, seen = await montar(audit)
    await session.execute(ToolCall(name="alfa.pagar", arguments=ARGS))
    ((aberto,),) = seen
    assert aberto.status == "started", "o handler viu o registro já aberto"


async def test_sem_auditoria_a_escrita_nao_executa() -> None:
    audit = SpyAudit(fail_begin=True)
    _kit, session, calls, _seen = await montar(audit)
    resultado = await session.execute(ToolCall(name="alfa.pagar", arguments=ARGS))
    assert resultado.status == "error" and "auditoria indisponível" in (resultado.error or "")
    assert calls.native == [], "nenhuma escrita sem registro (SC-002)"


async def test_fechamento_que_falha_deixa_started_e_o_resultado_segue() -> None:
    audit = SpyAudit(fail_finish=True)
    _kit, session, _calls, _seen = await montar(audit)
    resultado = await session.execute(ToolCall(name="alfa.pagar", arguments=ARGS))
    assert resultado.status == "ok"
    (record,) = await audit.query(AuditFilter())
    assert record.status == "started"


async def test_prazo_vencido_fica_registrado_como_timeout() -> None:
    audit = SpyAudit()
    _kit, session, _calls, _seen = await montar(audit, delay=5.0)
    resultado = await session.execute(ToolCall(name="alfa.pagar", arguments=ARGS))
    assert resultado.status == "timeout"
    (record,) = await audit.query(AuditFilter())
    assert record.status == "timeout"


async def test_duas_chamadas_iguais_dois_registros_e_leitura_nao_audita() -> None:
    audit = SpyAudit()
    _kit, session, _calls, _seen = await montar(audit)
    await session.execute(ToolCall(name="alfa.pagar", arguments=ARGS))
    await session.execute(ToolCall(name="alfa.pagar", arguments=ARGS))
    await session.execute(ToolCall(name="alfa.ler", arguments={}))
    assert [r.tool for r in await audit.query(AuditFilter())] == ["alfa.pagar", "alfa.pagar"]


async def test_escrita_de_mcp_tambem_e_auditada() -> None:
    audit = SpyAudit()
    servers = {"fin": FakeServer(tools=[mcp_tool("transferir", mutates=True)])}
    kit = build(servers=servers, audit=audit)
    session = await kit.service.open(grant(mcp=["fin"], write=["fin.transferir"]), context())
    await session.execute(ToolCall(name="fin.transferir", arguments={"texto": "x"}))
    (record,) = await audit.query(AuditFilter())
    assert (record.tool, record.kind, record.status) == ("fin.transferir", "mcp", "ok")
