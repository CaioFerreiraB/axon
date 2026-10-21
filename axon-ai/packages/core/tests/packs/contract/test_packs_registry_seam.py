"""Suíte de conformidade do seam Pack Registry (contracts/pack-runtime-api.md; US2 cenário 3; T020)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from packs_testkit import GOOD_CONFIG, load_runtime, make_good_pack, make_pack_class

from axon_ai.packs.adapters.data_dirs import LocalPackDataDirs
from axon_ai.packs.adapters.memory import InMemoryPackConfigSource, InMemoryPackSource
from axon_ai.packs.api import Composition, CompositionError, PackRegistry, PackStatus
from axon_ai.packs.ports import PackSettings
from axon_ai.packs.service import PackRuntime
from axon_ai_contracts import PackContext


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


def test_carga_entrega_o_data_dir_sem_criar_nem_preparar(tmp_path: Path) -> None:
    """US4 cen. 5 (ADR-041, R64): `<raiz>/<nome>` no `PackContext` dos hooks; nada criado, `prepare` nunca chamado."""
    seen: list[Path | None] = []

    def system_prompt(self: Any, ctx: PackContext) -> str:
        seen.append(ctx.data_dir)
        return "p"

    def prepare(self: Any, ctx: PackContext) -> None:
        raise AssertionError("a carga não chama prepare")

    root = tmp_path / "dados"
    runtime = PackRuntime(
        InMemoryPackSource.of(make_good_pack("alfa", system_prompt=system_prompt, prepare=prepare)),
        InMemoryPackConfigSource({"alfa": PackSettings(enabled=True, config=GOOD_CONFIG)}),
        LocalPackDataDirs(root),
    )
    runtime.load()
    assert seen == [root / "alfa"]
    assert not root.exists()

    seen.clear()
    load_runtime(
        make_good_pack("alfa", system_prompt=system_prompt),
        settings={"alfa": PackSettings(enabled=True, config=GOOD_CONFIG)},
    )
    assert seen == [None], "sem raiz, data_dir é None"
