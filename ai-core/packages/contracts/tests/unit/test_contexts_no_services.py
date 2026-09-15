"""Contextos sem serviços; Turn View só com os campos enumerados (US4 cenários 2 e 3, FR-019; T046)."""

from __future__ import annotations

import dataclasses

from ai_core_contracts import PackContext, TurnView, ValidatorContext

TURN_VIEW_FIELDS = {
    "request_id",
    "assistant",
    "reference_time",
    "question",
    "messages",
    "retrieved",
    "reranked",
    "generation_context",
    "tool_results",
    "answer",
    "citations",
    "own_slice",
    "dependency_slices",
}


def _field_names(cls: type) -> set[str]:
    return {field.name for field in dataclasses.fields(cls)}  # type: ignore[arg-type]


def test_contexts_carry_only_load_data() -> None:
    assert _field_names(ValidatorContext) == {"pack_name", "config"}
    assert _field_names(PackContext) == {"pack_name", "config"}


def test_validator_context_exposes_no_model_or_service() -> None:
    public = {name for name in dir(ValidatorContext(pack_name="p")) if not name.startswith("_")}
    assert public == {"pack_name", "config"}
    assert not any(word in name for name in public for word in ("model", "llm", "provider", "service", "client"))


def test_turn_view_has_only_enumerated_fields() -> None:
    assert _field_names(TurnView) == TURN_VIEW_FIELDS


def test_other_packs_slices_only_through_dependency_slices() -> None:
    slice_fields = {name for name in TURN_VIEW_FIELDS if "slice" in name}
    assert slice_fields == {"own_slice", "dependency_slices"}
