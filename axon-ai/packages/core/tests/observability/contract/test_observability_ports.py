"""Conformidade das portas (spec 009, T008): contracts/ports.md, memoria e JSONL, mais o Clock."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import pytest
from trace_testkit import AT, record

from axon_ai.observability.adapters.jsonl import JsonlTraceBackend, SystemClock
from axon_ai.observability.adapters.memory import FixedClock, InMemoryTraceBackend


class Backend(Protocol):
    def export(self, record: object) -> None: ...
    def read(self, request_id: str) -> object: ...


@pytest.fixture(params=["memory", "jsonl"])
def backend(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Backend]:
    if request.param == "memory":
        yield InMemoryTraceBackend()  # type: ignore[misc]
    else:
        yield JsonlTraceBackend(tmp_path)  # type: ignore[misc]


def test_round_trip_preserves_order(backend: Backend) -> None:
    for index in range(3):
        backend.export(record(at=AT + timedelta(seconds=index), step=index))
    read = list(backend.read("req-7f3a"))  # type: ignore[call-overload]
    assert [item.attributes["step"] for item in read] == [0, 1, 2]


def test_reads_only_the_requested_identifier(backend: Backend) -> None:
    backend.export(record("req-a", marker="a"))
    backend.export(record("req-b", marker="b"))
    backend.export(record("req-a", marker="a2"))
    assert [item.attributes["marker"] for item in backend.read("req-a")] == ["a", "a2"]  # type: ignore[call-overload]
    assert [item.attributes["marker"] for item in backend.read("req-b")] == ["b"]  # type: ignore[call-overload]


def test_unknown_identifier_is_empty(backend: Backend) -> None:
    assert list(backend.read("req-inexistente")) == []  # type: ignore[call-overload]


def test_nested_attributes_survive(backend: Backend) -> None:
    attributes = {"packs": ["a", "b"], "detail": {"n": 1, "ok": True, "x": None}, "ratio": 1.5}
    backend.export(record(**attributes))
    [item] = backend.read("req-7f3a")  # type: ignore[call-overload]
    assert dict(item.attributes) == attributes


def test_timezone_is_preserved(backend: Backend) -> None:
    backend.export(record(at=AT))
    [item] = backend.read("req-7f3a")  # type: ignore[call-overload]
    assert item.at.tzinfo is not None
    assert item.at == AT


def test_many_records_keep_order(backend: Backend) -> None:
    for index in range(300):
        backend.export(record(step=index))
    assert [item.attributes["step"] for item in backend.read("req-7f3a")] == list(range(300))  # type: ignore[call-overload]


def test_fixed_clock_repeats_the_instant() -> None:
    clock = FixedClock(AT)
    assert clock.now() == clock.now() == AT
    assert clock.now().tzinfo is not None


def test_system_clock_has_timezone_and_does_not_go_back() -> None:
    clock = SystemClock()
    first, second = clock.now(), clock.now()
    assert first.tzinfo is not None
    assert second >= first
    assert abs((second - datetime.now(UTC)).total_seconds()) < 5
