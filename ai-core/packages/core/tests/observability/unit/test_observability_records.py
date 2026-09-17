"""Serialização do registro (spec 009, T007): contracts/record-format.md."""

from __future__ import annotations

import dataclasses
import json

import pytest
from trace_testkit import AT, REFERENCE_TIME, failure, finished, model_call, started, validation

from ai_core.observability.api import TraceEvent
from ai_core.observability.domain.records import record_type, to_record

EVENTS = [started(), model_call(), validation(), failure(), finished()]


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (started(), "execution_started"),
        (model_call(), "model_call"),
        (validation(), "validation_run"),
        (failure(), "execution_error"),
        (finished(), "execution_finished"),
    ],
)
def test_record_type_is_snake_case(event: TraceEvent, expected: str) -> None:
    assert record_type(event) == expected


@pytest.mark.parametrize("event", EVENTS)
def test_record_has_the_three_fixed_fields(event: TraceEvent) -> None:
    record = to_record(event, AT)
    assert record.at == AT
    assert record.type == record_type(event)
    assert record.request_id == event.request_id
    assert "at" not in record.attributes and "type" not in record.attributes
    assert "request_id" not in record.attributes


@pytest.mark.parametrize("event", EVENTS)
def test_no_event_declares_a_reserved_field_name(event: TraceEvent) -> None:
    names = {field.name for field in dataclasses.fields(event)}
    assert not names & {"at", "type"}


def test_none_is_omitted() -> None:
    assert "reason" not in to_record(finished(reason=None), AT).attributes
    assert to_record(finished(reason="limite"), AT).attributes["reason"] == "limite"
    assert "finish_reason" not in to_record(model_call(finish_reason=None), AT).attributes


def test_collections_and_datetimes_become_json() -> None:
    attributes = to_record(started(packs=("b", "a")), AT).attributes
    assert attributes["packs"] == ["b", "a"]
    assert attributes["reference_time"] == REFERENCE_TIME.isoformat()
    flags = to_record(validation(flags=frozenset({"z", "a"}), issues=("x",)), AT).attributes
    assert flags["flags"] == ["a", "z"]
    assert flags["issues"] == ["x"]


def test_free_text_is_redacted() -> None:
    record = to_record(failure(message="401: {'Authorization': 'Bearer sk-abc123'}"), AT)
    assert "sk-abc123" not in str(record.attributes["message"])


@pytest.mark.parametrize("event", EVENTS)
def test_record_is_json_serializable(event: TraceEvent) -> None:
    record = to_record(event, AT)
    payload = {"at": record.at.isoformat(), "type": record.type, "request_id": record.request_id} | dict(
        record.attributes
    )
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload
