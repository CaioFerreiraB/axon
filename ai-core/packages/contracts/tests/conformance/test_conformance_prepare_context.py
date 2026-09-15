"""Conformidade de prepare_context: fatia JSON, determinística, com filtros válidos (FR-010, FR-012; T047)."""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from packs import make_pack

from ai_core_contracts import PackManifest, TurnView
from ai_core_contracts.testing import check_pack


def _codes(pack: object) -> list[str]:
    return [issue.code for issue in check_pack(pack, check_distribution=False).issues]


def _prepare(result: Any) -> Any:
    async def prepare_context(self: Any, view: TurnView, ctx: Any) -> Any:
        return result

    return prepare_context


def test_valid_update_passes() -> None:
    update = {"ramo": "x", "retrieval_filters": {"effective_on": "2026-01-01", "tipos": ["manual"]}}
    assert _codes(make_pack(prepare_context=_prepare(update))) == []


def test_update_must_be_a_mapping() -> None:
    assert _codes(make_pack(prepare_context=_prepare(["não", "é", "mapeamento"]))) == ["prepare_context.not_mapping"]


def test_update_must_be_json() -> None:
    update = {"quando": datetime(2026, 1, 1, tzinfo=UTC)}
    assert _codes(make_pack(prepare_context=_prepare(update))) == ["prepare_context.not_json"]


def test_retrieval_filters_must_be_a_json_mapping() -> None:
    assert _codes(make_pack(prepare_context=_prepare({"retrieval_filters": ["x"]}))) == [
        "prepare_context.retrieval_filters.invalid"
    ]


def test_update_must_be_deterministic() -> None:
    counter = itertools.count()

    async def prepare_context(self: Any, view: TurnView, ctx: Any) -> Mapping[str, Any]:
        return {"n": next(counter)}

    assert _codes(make_pack(prepare_context=prepare_context)) == ["prepare_context.non_deterministic"]


def test_default_views_carry_only_declared_dependency_slices() -> None:
    seen: list[Mapping[str, Any]] = []

    async def prepare_context(self: Any, view: TurnView, ctx: Any) -> Mapping[str, Any]:
        seen.append(view.dependency_slices)
        return {}

    with_dependency = make_pack(
        manifest=PackManifest(name="good", version="0.1.0", depends_on=("outro",)), prepare_context=prepare_context
    )
    assert _codes(with_dependency) == []
    assert seen[-1] == {"outro": {}}
    assert _codes(make_pack(prepare_context=prepare_context)) == []
    assert seen[-1] == {}


def test_reading_an_undeclared_slice_fails() -> None:
    async def prepare_context(self: Any, view: TurnView, ctx: Any) -> Mapping[str, Any]:
        return {"lido": view.dependency_slices["nao_declarado"]}

    report = check_pack(make_pack(prepare_context=prepare_context), check_distribution=False)
    [issue] = report.issues
    assert (issue.code, issue.subject) == ("hook.raised", "hook:prepare_context")
