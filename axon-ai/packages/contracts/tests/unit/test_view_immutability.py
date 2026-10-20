"""Turn View imutável em profundidade e igual entre produtores (US4 cenário 1 e independent test; T045)."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

import pytest

from axon_ai_contracts import JSONValue, PackBase, PackContext, PackManifest, ToolResult, TurnView
from axon_ai_contracts.testing import REFERENCE_TIME, pack_context, turn_view


def _mutable_data() -> dict[str, object]:
    return {
        "question": "qual a regra?",
        "messages": [{"role": "user", "content": "oi"}],
        "own_slice": {"filtros": {"ramo": ["a"]}},
        "dependency_slices": {"outro": {"x": 1}},
        "tool_results": [ToolResult(content={"rows": [1, 2]})],
    }


def _manual_view(data: dict[str, object]) -> TurnView:
    return TurnView(request_id="req-test", assistant="test-assistant", reference_time=REFERENCE_TIME, **data)  # type: ignore[arg-type]


def test_mutating_the_inputs_does_not_change_the_view() -> None:
    data = _mutable_data()
    view = _manual_view(data)
    data["messages"].append({"role": "user", "content": "x"})  # type: ignore[attr-defined]
    data["own_slice"]["filtros"]["ramo"].append("b")  # type: ignore[index]
    data["dependency_slices"]["outro"]["x"] = 2  # type: ignore[index]
    assert len(view.messages) == 1
    assert view.own_slice == {"filtros": {"ramo": ("a",)}}
    assert view.dependency_slices == {"outro": {"x": 1}}
    assert view.tool_results[0].content == {"rows": (1, 2)}


def test_fields_and_items_cannot_be_assigned() -> None:
    view = _manual_view(_mutable_data())
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.question = "outra"  # type: ignore[misc]
    with pytest.raises(TypeError):
        view.own_slice["novo"] = 1  # type: ignore[index]
    with pytest.raises(TypeError):
        view.own_slice["filtros"]["ramo"] = ()  # type: ignore[index]
    with pytest.raises(TypeError):
        view.messages[0]["content"] = "trocado"  # type: ignore[typeddict-readonly-mutated]


class _EchoPack(PackBase):
    name = "echo_pack"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        return PackManifest(name="echo_pack", version="0.1.0")

    async def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]:
        return {"pergunta": view.question, "mensagens": len(view.messages), "filtros": view.own_slice.get("filtros")}


async def test_two_producers_give_equal_views_and_equal_hook_results() -> None:
    from_fixture = turn_view(**_mutable_data())  # type: ignore[arg-type]
    by_hand = _manual_view(_mutable_data())
    assert from_fixture == by_hand
    pack = _EchoPack()
    ctx = pack_context(pack.name)
    assert await pack.prepare_context(from_fixture, ctx) == await pack.prepare_context(by_hand, ctx)
