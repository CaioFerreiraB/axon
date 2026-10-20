from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from axon_ai_contracts._freeze import (
    freeze,
    freeze_mapping,
    freeze_sequence,
    is_json_value,
    require_aware,
    require_non_empty,
)


def test_changing_the_original_does_not_change_the_frozen_copy() -> None:
    original = {"a": [1, {"b": 2}], "c": {"d"}}
    frozen = freeze_mapping(original)
    original["a"].append(3)  # type: ignore[attr-defined]
    original["a"][1]["b"] = 99  # type: ignore[index]
    original["z"] = 0
    assert frozen == {"a": (1, {"b": 2}), "c": frozenset({"d"})}


def test_nested_mapping_rejects_item_assignment() -> None:
    frozen = freeze_mapping({"outer": {"inner": 1}})
    with pytest.raises(TypeError):
        frozen["outer"]["inner"] = 2  # type: ignore[index]
    with pytest.raises(TypeError):
        frozen["new"] = 1  # type: ignore[index]


def test_freeze_keeps_leaves() -> None:
    marker = object()
    assert freeze("texto") == "texto"
    assert freeze(b"bytes") == b"bytes"
    assert freeze(marker) is marker
    assert isinstance(freeze({"x": 1}), MappingProxyType)
    assert freeze([1, [2]]) == (1, (2,))


def test_freeze_sequence_rejects_text_and_mappings() -> None:
    with pytest.raises(TypeError):
        freeze_sequence("abc")
    with pytest.raises(TypeError):
        freeze_sequence({"a": 1})
    assert freeze_sequence([{"a": 1}]) == ({"a": 1},)


def test_freeze_mapping_rejects_non_mapping() -> None:
    with pytest.raises(TypeError):
        freeze_mapping([("a", 1)])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [None, "x", 1, 1.5, True, [], (), {}, {"a": [1, "b", {"c": None}]}, MappingProxyType({"k": (1, 2)})],
)
def test_is_json_value_accepts(value: object) -> None:
    assert is_json_value(value)


@pytest.mark.parametrize(
    "value",
    [datetime(2026, 1, 1, tzinfo=UTC), {1: "chave int"}, {"a": {1, 2}}, {"a": object()}, b"bytes", {"x"}],
)
def test_is_json_value_rejects(value: object) -> None:
    assert not is_json_value(value)


def test_require_helpers() -> None:
    require_non_empty("campo", "ok")
    with pytest.raises(ValueError):
        require_non_empty("campo", "  ")
    require_aware("quando", datetime(2026, 1, 1, tzinfo=UTC))
    with pytest.raises(ValueError):
        require_aware("quando", datetime(2026, 1, 1))
    with pytest.raises(TypeError):
        require_aware("quando", "2026-01-01")
