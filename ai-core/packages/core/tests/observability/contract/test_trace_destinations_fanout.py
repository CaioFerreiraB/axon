"""T053 — fan-out de destinos no `TraceService` (ADR-034; research R28, R29; SC-007)."""

from __future__ import annotations

import pytest
from trace_testkit import AT, exchange, finished, model_call, started

from ai_core.observability.adapters.memory import (
    FailingDestination,
    FixedClock,
    InMemoryTraceBackend,
    RecordingDestination,
)
from ai_core.observability.service import TraceService

pytestmark = pytest.mark.us7


def _service(*destinations: RecordingDestination, capture: bool = False) -> tuple[TraceService, InMemoryTraceBackend]:
    primary = InMemoryTraceBackend()
    service = TraceService(
        exporter=primary, reader=primary, clock=FixedClock(AT), destinations=destinations, capture=lambda: capture
    )
    return service, primary


def test_cada_registro_vai_ao_primario_e_a_todos_os_destinos() -> None:
    usage, langfuse = RecordingDestination("usage"), RecordingDestination("langfuse", accepts_content=True)
    service, primary = _service(usage, langfuse)
    for event in (started(), model_call(), finished()):
        service.emit(event)
    expected = ["execution_started", "model_call", "execution_finished"]
    assert [r.type for r in primary.read("req-7f3a")] == expected
    assert [r.type for r in usage.records] == expected == [r.type for r in langfuse.records]


def test_destino_que_falha_fica_isolado_e_contado() -> None:
    broken, healthy = FailingDestination("quebrado"), RecordingDestination("usage")
    service, primary = _service(broken, healthy)
    service.emit(started())
    service.emit(model_call())
    assert len(primary.read("req-7f3a")) == 2 and len(healthy.records) == 2
    assert service.destination_failures("quebrado") == 2 and service.dropped_events() == 0


def test_conteudo_descartado_com_a_captura_desligada() -> None:
    usage, langfuse = RecordingDestination("usage"), RecordingDestination("langfuse", accepts_content=True)
    service, primary = _service(usage, langfuse, capture=False)
    service.emit(exchange())
    assert primary.read("req-7f3a") == () and usage.records == [] and langfuse.records == []


def test_conteudo_ligado_so_para_quem_aceita_e_nunca_no_primario() -> None:
    usage, langfuse = RecordingDestination("usage"), RecordingDestination("langfuse", accepts_content=True)
    service, primary = _service(usage, langfuse, capture=True)
    service.emit(exchange())
    assert primary.read("req-7f3a") == ()  # SC-007: nem memória nem JSONL guardam texto de prompt e resposta
    assert usage.records == []
    (record,) = langfuse.records
    assert record.type == "model_exchange" and "sk-segredo-123" not in str(record.attributes)


def test_emit_nunca_levanta_nem_com_a_politica_de_captura_quebrada() -> None:
    langfuse = RecordingDestination("langfuse", accepts_content=True)

    def broken() -> bool:
        raise RuntimeError("ajustes indisponíveis")

    primary = InMemoryTraceBackend()
    service = TraceService(
        exporter=primary, reader=primary, clock=FixedClock(AT), destinations=(langfuse,), capture=broken
    )
    service.emit(exchange())
    assert langfuse.records == []


async def test_flush_esvazia_os_destinos_e_isola_falhas() -> None:
    class BrokenFlush(RecordingDestination):
        async def flush(self) -> None:
            raise OSError("banco fora do ar")

    good, bad = RecordingDestination("usage"), BrokenFlush("langfuse")
    service, _ = _service(good, bad)
    await service.flush()
    assert good.flushes == 1 and service.destination_failures("langfuse") == 1
