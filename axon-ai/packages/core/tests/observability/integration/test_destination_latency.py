"""T065 — SC-006: com o Langfuse travado e o banco de uso lento, `emit` não espera rede nem banco.

Medido em 2026-10-14 (research R32, "Medição"): ~10 µs por evento só com o primário, ~11,5 µs com o destino de uso e
~22,5 µs com uso e Langfuse — o mapeamento para spans custa CPU, mas nada espera I/O. O teste fixa um teto absoluto por
evento, folgado para a CI.
"""

from __future__ import annotations

import time

import pytest
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from trace_testkit import AT, finished, model_call, started

from axon_ai.observability.adapters.langfuse import LangfuseDestination, OtelLangfuseTransport
from axon_ai.observability.adapters.memory import FixedClock, InMemoryTraceBackend
from axon_ai.observability.adapters.usage import UsageDestination
from axon_ai.observability.ports import LangfuseCredentials
from axon_ai.observability.service import TraceService

pytestmark = pytest.mark.us6


class Hung(SpanExporter):
    def export(self, spans: object) -> SpanExportResult:  # type: ignore[override]
        time.sleep(30)
        return SpanExportResult.SUCCESS


class SlowStore:
    async def append(self, calls: object, executions: object) -> None:
        import asyncio

        await asyncio.sleep(30)


def _emit_all(service: TraceService, count: int) -> float:
    start = time.perf_counter()
    for index in range(count // 3):
        rid = f"r{index}"
        service.emit(started(request_id=rid))
        service.emit(model_call(request_id=rid))
        service.emit(finished(request_id=rid))
    return time.perf_counter() - start


def test_destinos_travados_nao_atrasam_quem_emite() -> None:
    baseline_backend = InMemoryTraceBackend()
    baseline = TraceService(exporter=baseline_backend, reader=baseline_backend, clock=FixedClock(AT))
    alone = min(_emit_all(baseline, 1_002) for _ in range(3))

    transport = OtelLangfuseTransport(exporter_factory=lambda _c: Hung(), queue=64, batch=8, delay_ms=1)
    langfuse = LangfuseDestination(transport, clock=lambda: AT)
    langfuse.configure(LangfuseCredentials(host="https://lf.test", public_key="pk", secret_key="sk"))
    usage = UsageDestination(store=SlowStore(), origin="production", clock=FixedClock(AT))  # type: ignore[arg-type]
    backend = InMemoryTraceBackend()
    service = TraceService(exporter=backend, reader=backend, clock=FixedClock(AT), destinations=(usage, langfuse))
    with_destinations = min(_emit_all(service, 1_002) for _ in range(3))
    transport.reconfigure(None)
    per_event = with_destinations / 1_002
    # com o exportador travado 30 s e o banco 30 s, qualquer espera de I/O estouraria isto em ordens de grandeza
    assert per_event < 0.0005, (alone / 1_002, per_event)
