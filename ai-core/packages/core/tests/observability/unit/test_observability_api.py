"""Seam Trace Sink: validação, imutabilidade e superfície pública (spec 009, T005)."""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

import pytest
from trace_testkit import REFERENCE_TIME, failure, finished, model_call, started, validation

import ai_core.observability.api as api_module
from ai_core.observability.api import ExecutionStarted, ModelCall, ValidationRun

EXPECTED_NAMES = {
    "ExecutionStarted",
    "ModelCall",
    "ValidationRun",
    "ToolCall",
    "ControllerDecision",
    "DecisionAction",
    "ExecutionError",
    "ExecutionFinished",
    "TraceEvent",
    "TraceRecord",
    "Trace",
    "TraceSink",
    "TraceQuery",
    "TraceQueryUnavailable",
}


def test_valid_events() -> None:
    for event in (started(), model_call(), validation(), failure(), finished()):
        assert event.request_id == "req-7f3a"


def test_events_are_frozen_and_hashable() -> None:
    event = finished()
    with pytest.raises(AttributeError):
        event.ok = False  # type: ignore[misc]
    assert {event, finished()} == {event}


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_blank_request_id_is_rejected(blank: str) -> None:
    for factory in (started, model_call, validation, failure, finished):
        with pytest.raises(ValueError, match="request_id"):
            factory(blank)


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (started, "assistant"),
        (started, "flow"),
        (model_call, "role"),
        (model_call, "provider"),
        (model_call, "model"),
        (validation, "pack"),
        (validation, "validator"),
        (failure, "stage"),
        (failure, "kind"),
    ],
)
def test_blank_text_fields_are_rejected(factory: object, field: str) -> None:
    with pytest.raises(ValueError, match=field):
        factory(**{field: "  "})  # type: ignore[operator]


def test_reference_time_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        started(reference_time=datetime(2026, 9, 17))


@pytest.mark.parametrize(
    ("factory", "field"),
    [(model_call, "duration_ms"), (model_call, "input_tokens"), (model_call, "output_tokens")],
)
def test_negative_numbers_are_rejected(factory: object, field: str) -> None:
    with pytest.raises(ValueError, match=field):
        factory(**{field: -1})  # type: ignore[operator]


def test_negative_duration_on_finished_is_rejected() -> None:
    with pytest.raises(ValueError, match="duration_ms"):
        finished(duration_ms=-0.1)


def test_optional_token_counts_default_to_none() -> None:
    event = ModelCall(request_id="req-1", role="generation", provider="ollama", model="m", duration_ms=1.0)
    assert (event.input_tokens, event.output_tokens, event.finish_reason) == (None, None, None)


def test_collections_are_immutable() -> None:
    event = started(packs=("a", "b"))
    assert isinstance(event.packs, tuple)
    run = ValidationRun(request_id="req-1", pack="p", validator="v", ok=False, issues=("x",), flags=frozenset({"f"}))
    assert isinstance(run.issues, tuple) and isinstance(run.flags, frozenset)
    assert ExecutionStarted(request_id="req-1", assistant="a", flow="chat", reference_time=REFERENCE_TIME).packs == ()


def test_public_names_match_the_contract() -> None:
    public = {name for name in vars(api_module) if not name.startswith("_")}
    imported = {"Mapping", "dataclass", "datetime", "Final", "Literal", "Protocol", "JSONValue", "annotations"}
    assert public - imported == EXPECTED_NAMES


def test_api_imports_only_stdlib_and_contracts() -> None:
    """O seam não pode trazer biblioteca de observabilidade nem outro módulo do core (FR-013, research R1)."""
    source = Path(api_module.__file__).read_text(encoding="utf-8")
    roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    assert roots <= {"__future__", "collections", "dataclasses", "datetime", "typing", "ai_core_contracts"}
