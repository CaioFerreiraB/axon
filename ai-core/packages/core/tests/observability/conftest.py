"""Fixtures dos testes de trace (spec 009). As fábricas ficam em `trace_testkit` (mesmo padrão de `packs_testkit`)."""

from __future__ import annotations

import pytest
from trace_testkit import AT

from ai_core.observability.adapters.memory import FixedClock, InMemoryTraceBackend
from ai_core.observability.service import TraceService


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(AT)


@pytest.fixture
def backend() -> InMemoryTraceBackend:
    return InMemoryTraceBackend()


@pytest.fixture
def service(backend: InMemoryTraceBackend, clock: FixedClock) -> TraceService:
    return TraceService(exporter=backend, reader=backend, clock=clock)
