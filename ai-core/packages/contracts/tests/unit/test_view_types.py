from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_core_contracts.retrieval import Chunk
from ai_core_contracts.view import TurnView

NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)


def test_minimal_turn_view_has_empty_defaults() -> None:
    view = TurnView(request_id="req-1", assistant="a", reference_time=NOW, question="q")
    assert view.messages == () and view.retrieved == () and view.generation_context == ()
    assert view.answer is None
    assert view.own_slice == {} and view.dependency_slices == {}


def test_turn_view_converts_sequences_to_tuples() -> None:
    chunk = Chunk(chunk_id="c1", text="t", score=1.0, document="d")
    view = TurnView(
        request_id="req-1",
        assistant="a",
        reference_time=NOW,
        question="q",
        retrieved=[chunk],
        messages=[{"role": "user", "content": "oi"}],
        citations=[{"chunk_id": "c1"}],
    )
    assert view.retrieved == (chunk,)
    assert isinstance(view.messages, tuple) and view.messages[0]["content"] == "oi"
    assert view.citations[0]["chunk_id"] == "c1"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"request_id": "", "assistant": "a", "reference_time": NOW},
        {"request_id": "r", "assistant": " ", "reference_time": NOW},
        {"request_id": "r", "assistant": "a", "reference_time": datetime(2026, 1, 1)},
    ],
)
def test_turn_view_rejects_invalid_construction(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        TurnView(question="q", **kwargs)  # type: ignore[arg-type]
