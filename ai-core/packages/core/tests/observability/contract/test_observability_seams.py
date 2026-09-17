"""Conformidade dos seams Trace Sink e Trace (spec 009, T009): contracts/trace-api.md."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from trace_testkit import AT, FailingTraceExporter, failure, finished, model_call, started, validation

from ai_core.observability.adapters.memory import FixedClock, InMemoryTraceBackend
from ai_core.observability.api import TraceQueryUnavailable
from ai_core.observability.service import TraceService


def test_emit_returns_nothing_for_every_event(service: TraceService) -> None:
    for event in (started(), model_call(), validation(), failure(), finished()):
        assert service.emit(event) is None


def test_instant_comes_from_the_injected_clock(backend: InMemoryTraceBackend) -> None:
    other = datetime(2030, 1, 2, 3, 4, tzinfo=UTC)
    service = TraceService(exporter=backend, reader=backend, clock=FixedClock(other))
    service.emit(finished())
    [record] = service.trace("req-7f3a").records
    assert record.at == other


def test_order_of_emission_is_preserved(service: TraceService) -> None:
    service.emit(started())
    service.emit(model_call())
    service.emit(validation())
    service.emit(finished())
    trace = service.trace("req-7f3a")
    assert trace.request_id == "req-7f3a"
    assert [record.type for record in trace.records] == [
        "execution_started",
        "model_call",
        "validation_run",
        "execution_finished",
    ]


def test_trace_of_unknown_request_is_empty(service: TraceService) -> None:
    trace = service.trace("req-nao-vista")
    assert trace.request_id == "req-nao-vista"
    assert trace.records == ()


def test_query_without_reader_is_explicit(clock: FixedClock) -> None:
    service = TraceService(exporter=InMemoryTraceBackend(), reader=None, clock=clock)
    with pytest.raises(TraceQueryUnavailable, match="InMemoryTraceBackend"):
        service.trace("req-7f3a")


def test_exporter_failure_never_propagates(clock: FixedClock, caplog: pytest.LogCaptureFixture) -> None:
    exporter = FailingTraceExporter()
    service = TraceService(exporter=exporter, reader=None, clock=clock)
    with caplog.at_level(logging.WARNING, logger="ai_core.observability"):
        service.emit(started())
        service.emit(finished())
    assert exporter.attempts == 2
    assert service.dropped_events() == 2
    assert "OSError" in caplog.text


def test_emission_continues_after_a_failure(backend: InMemoryTraceBackend, clock: FixedClock) -> None:
    """Uma falha de backend não pode deixar o sink inutilizável."""

    class FlakyExporter:
        def __init__(self) -> None:
            self.calls = 0

        def export(self, record: object) -> None:
            self.calls += 1
            if self.calls == 1:
                raise OSError("falha transitória")
            backend.export(record)  # type: ignore[arg-type]

    service = TraceService(exporter=FlakyExporter(), reader=backend, clock=clock)
    service.emit(started())
    service.emit(finished())
    assert service.dropped_events() == 1
    assert [record.type for record in service.trace("req-7f3a").records] == ["execution_finished"]


def test_dropped_events_starts_at_zero_and_never_decreases(service: TraceService) -> None:
    assert service.dropped_events() == 0
    service.emit(finished())
    assert service.dropped_events() == 0


def test_credential_in_error_message_is_not_recorded(service: TraceService) -> None:
    """US1 cenário 2: o que chega com credencial é gravado redigido (FR-002)."""
    service.emit(
        failure(message="401 Unauthorized: {'Authorization': 'Bearer sk-abc123'} em https://user:s3nha@api/v1")
    )
    [record] = service.trace("req-7f3a").records
    message = str(record.attributes["message"])
    assert "sk-abc123" not in message
    assert "s3nha" not in message
    assert "«redigido»" in message


def test_records_carry_the_clock_instant_and_the_reference_time(service: TraceService) -> None:
    """O instante do evento e a data de referência da execução são coisas diferentes (ADR-013)."""
    service.emit(started())
    [record] = service.trace("req-7f3a").records
    assert record.at == AT
    assert record.attributes["reference_time"] == "2026-09-17T00:00:00+00:00"
