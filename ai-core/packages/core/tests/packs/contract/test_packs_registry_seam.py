"""Suíte de conformidade do seam Pack Registry (contracts/pack-runtime-api.md; US2 cenário 3; T020)."""

from __future__ import annotations

from typing import Any

import pytest
from packs_testkit import GOOD_CONFIG, load_runtime, make_good_pack, make_pack_class

from ai_core.packs.api import Composition, CompositionError, PackRegistry, PackStatus
from ai_core.packs.ports import PackSettings


@pytest.fixture
def registry() -> PackRegistry:
    runtime: Any = load_runtime(
        make_good_pack("alfa"),
        make_good_pack("beta"),
        make_pack_class("desligado"),
        make_pack_class("quebrado", "0.3"),
        settings={
            "alfa": PackSettings(enabled=True, config=GOOD_CONFIG),
            "beta": PackSettings(enabled=True, config=GOOD_CONFIG),
            "quebrado": PackSettings(enabled=True),
        },
    )
    return runtime


def test_entries_are_sorted_and_immutable(registry: PackRegistry) -> None:
    entries = registry.entries()
    assert [entry.name for entry in entries] == ["alfa", "beta", "desligado", "quebrado"]
    assert isinstance(entries, tuple)
    assert [entry.status for entry in entries] == [
        PackStatus.ENABLED,
        PackStatus.ENABLED,
        PackStatus.DISABLED,
        PackStatus.ERROR,
    ]


def test_entry_lookup(registry: PackRegistry) -> None:
    assert registry.entry("alfa") is not None
    assert registry.entry("inexistente") is None


def test_valid_composition_keeps_the_order(registry: PackRegistry) -> None:
    assert registry.compose(["beta", "alfa"]) == Composition(packs=("beta", "alfa"))


@pytest.mark.parametrize(
    ("names", "fragment", "packs"),
    [
        (["alfa", "inexistente"], "'inexistente' não está instalado", ("inexistente",)),
        (["desligado"], "'desligado' está desabilitado", ("desligado",)),
        (["quebrado"], "requer axon-ai-contracts>=0.3", ("quebrado",)),
        (["alfa", "alfa"], "'alfa' aparece mais de uma vez", ("alfa",)),
    ],
)
def test_compose_refuses_unavailable_packs(
    registry: PackRegistry, names: list[str], fragment: str, packs: tuple[str, ...]
) -> None:
    with pytest.raises(CompositionError) as excinfo:
        registry.compose(names)
    assert fragment in str(excinfo.value)
    assert excinfo.value.packs == packs
