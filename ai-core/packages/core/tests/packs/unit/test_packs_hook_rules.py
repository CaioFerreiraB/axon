"""Regras puras do Pack Hooks e da ordem de composição (FR-008, FR-009, research R7/R8; T024)."""

from __future__ import annotations

import pytest

from ai_core.packs.api import PackCapabilities, PackEntry, PackStatus
from ai_core.packs.domain.composition import composition_error
from ai_core.packs.domain.hooks import apply_validation, merge_slice, scope_view
from axon_ai_contracts import ValidationResult
from axon_ai_contracts.testing import turn_view


def test_scope_view_keeps_only_own_and_declared_slices() -> None:
    slices = {"a": {"x": 1}, "b": {"y": 2}, "c": {"z": 3}}
    view = scope_view(turn_view(question="q"), "b", ("a",), slices)
    assert view.own_slice == {"y": 2}
    assert view.dependency_slices == {"a": {"x": 1}}
    assert "c" not in view.dependency_slices
    assert view.question == "q"


def test_scope_view_for_pack_without_slice_yet() -> None:
    view = scope_view(turn_view(), "novo", (), {})
    assert view.own_slice == {} and view.dependency_slices == {}


def test_merge_slice_is_shallow() -> None:
    merged = merge_slice({"a": 1, "b": {"x": 1}}, {"b": {"y": 2}, "c": 3})
    assert merged == {"a": 1, "b": {"y": 2}, "c": 3}


@pytest.mark.parametrize("update", [["nao", "mapeamento"], {"quando": object()}, {1: "chave int"}])
def test_merge_slice_rejects_non_json(update: object) -> None:
    with pytest.raises(TypeError):
        merge_slice({}, update)


def test_apply_validation_threads_answer_and_citations() -> None:
    view = turn_view(answer="original", citations=[{"chunk_id": "c1"}])
    unchanged = apply_validation(view, ValidationResult(ok=True))
    assert unchanged.answer == "original" and unchanged.citations[0]["chunk_id"] == "c1"
    changed = apply_validation(view, ValidationResult(ok=False, answer="com aviso", citations=[]))
    assert changed.answer == "com aviso" and changed.citations == ()


def _enabled(name: str, depends_on: tuple[str, ...] = ()) -> PackEntry:
    capabilities = PackCapabilities(
        system_prompt=False,
        tools=(),
        retrievers=(),
        reranker=False,
        validators=(),
        preferred_flow=None,
        depends_on=depends_on,
        requires_collections=(),
    )
    return PackEntry(
        name=name,
        version="0.1.0",
        contract_version="0.2",
        origin="code",
        status=PackStatus.ENABLED,
        capabilities=capabilities,
    )


def test_dependency_must_come_before_the_dependent() -> None:
    entries = {"a": _enabled("a"), "b": _enabled("b", ("a",))}
    assert composition_error(("a", "b"), entries) is None
    before = composition_error(("b", "a"), entries)
    assert before is not None and before[1] == ("b", "a") and "precisa vir antes" in before[0]
    absent = composition_error(("b",), entries)
    assert absent is not None and absent[1] == ("b", "a") and "não está na composição" in absent[0]
