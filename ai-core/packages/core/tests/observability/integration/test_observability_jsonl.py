"""Backend JSONL em disco (spec 009, T010): contracts/record-format.md e quickstart §5."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from trace_testkit import AT, finished, started

from ai_core.observability.adapters.jsonl import JsonlTraceBackend
from ai_core.observability.adapters.memory import FixedClock
from ai_core.observability.service import TraceService


def _service(directory: Path, at: datetime) -> TraceService:
    backend = JsonlTraceBackend(directory)
    return TraceService(exporter=backend, reader=backend, clock=FixedClock(at))


def test_file_is_named_after_the_record_date(tmp_path: Path) -> None:
    _service(tmp_path, AT).emit(finished())
    assert [path.name for path in tmp_path.iterdir()] == ["trace-2026-09-17.jsonl"]


def test_directory_is_created_when_missing(tmp_path: Path) -> None:
    target = tmp_path / "traces" / "nested"
    _service(target, AT).emit(finished())
    assert (target / "trace-2026-09-17.jsonl").exists()


def test_every_line_is_valid_json_with_the_fixed_fields(tmp_path: Path) -> None:
    service = _service(tmp_path, AT)
    service.emit(started())
    service.emit(finished())
    lines = (tmp_path / "trace-2026-09-17.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line, expected_type in zip(lines, ("execution_started", "execution_finished"), strict=True):
        payload = json.loads(line)
        assert payload["type"] == expected_type
        assert payload["request_id"] == "req-7f3a"
        assert datetime.fromisoformat(payload["at"]) == AT


def test_writing_twice_appends(tmp_path: Path) -> None:
    _service(tmp_path, AT).emit(started())
    _service(tmp_path, AT).emit(finished())
    assert len((tmp_path / "trace-2026-09-17.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_records_rotate_by_day_and_reading_finds_both(tmp_path: Path) -> None:
    late = datetime(2026, 9, 17, 23, 50, tzinfo=UTC)
    _service(tmp_path, late).emit(started("req-a"))
    _service(tmp_path, late + timedelta(minutes=20)).emit(finished("req-b"))
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "trace-2026-09-17.jsonl",
        "trace-2026-09-18.jsonl",
    ]
    service = _service(tmp_path, late)
    assert [record.type for record in service.trace("req-a").records] == ["execution_started"]
    assert [record.type for record in service.trace("req-b").records] == ["execution_finished"]


def test_corrupted_line_is_skipped_with_a_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """US1 cenário 3: arquivo truncado por queda de processo não impede consultar o resto."""
    service = _service(tmp_path, AT)
    service.emit(started())
    path = tmp_path / "trace-2026-09-17.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"at": "2026-09-17T14:00:00+00:00", "type": "execu\n')
    service.emit(finished())
    with caplog.at_level(logging.WARNING, logger="ai_core.observability"):
        records = service.trace("req-7f3a").records
    assert [record.type for record in records] == ["execution_started", "execution_finished"]
    assert "linha" in caplog.text.lower()


def test_reading_ignores_unrelated_files(tmp_path: Path) -> None:
    (tmp_path / "README.txt").write_text("nada a ver", encoding="utf-8")
    service = _service(tmp_path, AT)
    service.emit(finished())
    assert len(service.trace("req-7f3a").records) == 1


def test_accents_are_written_as_text(tmp_path: Path) -> None:
    _service(tmp_path, AT).emit(finished(reason="execução concluída"))
    content = (tmp_path / "trace-2026-09-17.jsonl").read_text(encoding="utf-8")
    assert "execução concluída" in content
