"""Fixtures do kit de testes: defaults determinísticos e objetos congelados (T018)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from axon_ai_contracts.testing import (
    REFERENCE_TIME,
    chunk,
    pack_context,
    tool_invocation,
    turn_view,
    validator_context,
)


def test_reference_time_is_fixed_and_aware() -> None:
    assert datetime(2026, 1, 1, 12, 0, tzinfo=UTC) == REFERENCE_TIME


def test_turn_view_defaults() -> None:
    view = turn_view()
    assert (view.request_id, view.assistant, view.reference_time) == ("req-test", "test-assistant", REFERENCE_TIME)
    assert view.question == ""
    assert view.messages == () and view.retrieved == () and view.citations == ()
    assert view.own_slice == {} and view.dependency_slices == {}


def test_turn_view_overrides_are_frozen() -> None:
    view = turn_view(question="q", own_slice={"a": [1]}, dependency_slices={"outro": {"b": 2}})
    assert view.own_slice == {"a": (1,)}
    with pytest.raises(TypeError):
        view.dependency_slices["outro"]["b"] = 3  # type: ignore[index]


def test_chunk_defaults() -> None:
    item = chunk()
    assert (item.chunk_id, item.document, item.score, item.text) == ("doc#1", "doc", 1.0, "")
    assert chunk("x", page=3).page == 3


def test_contexts_and_invocation() -> None:
    assert pack_context("p").config == {}
    assert validator_context("p", {"k": "v"}).config == {"k": "v"}
    invocation = tool_invocation({"text": "oi"})
    assert invocation.arguments == {"text": "oi"}
    assert invocation.reference_time == REFERENCE_TIME
    assert invocation.request_id == "req-test"
