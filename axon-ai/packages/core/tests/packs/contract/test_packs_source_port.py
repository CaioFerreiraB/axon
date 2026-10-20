"""Conformidade da porta PackSource: adapter em memória e entry points reais (contracts/ports.md; T008)."""

from __future__ import annotations

import textwrap
import types
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pytest
from packs_testkit import GOOD_MODULE, FakeDistributions

from axon_ai.packs.adapters.entry_points import EntryPointPackSource
from axon_ai.packs.adapters.memory import InMemoryPackSource
from axon_ai.packs.ports import DiscoveredPack, PackSource


@dataclass(frozen=True)
class FakeDist:
    distribution: str
    version: str
    entry_name: str
    module: str
    source: str
    class_name: str


def _memory(dists: Sequence[FakeDist], fake: FakeDistributions) -> PackSource:
    def loader(dist: FakeDist) -> Callable[[], object]:
        def load() -> object:
            module = types.ModuleType(dist.module)
            exec(textwrap.dedent(dist.source), module.__dict__)
            return getattr(module, dist.class_name)

        return load

    entries = [
        DiscoveredPack(name=d.entry_name, distribution=d.distribution, version=d.version, load=loader(d)) for d in dists
    ]
    return InMemoryPackSource(sorted(entries, key=lambda e: (e.name, e.distribution)))


def _entry_points(dists: Sequence[FakeDist], fake: FakeDistributions) -> PackSource:
    for d in dists:
        fake.add(
            d.distribution,
            version=d.version,
            entry_points={d.entry_name: f"{d.module}:{d.class_name}"},
            modules={d.module: d.source},
        )
    return EntryPointPackSource()


@pytest.fixture(params=[_memory, _entry_points], ids=["memory", "entry_points"])
def build(request: pytest.FixtureRequest, fake_distributions: FakeDistributions) -> Callable[..., PackSource]:
    factory = request.param
    return lambda *dists: factory(dists, fake_distributions)


def _ours(entries: Sequence[DiscoveredPack]) -> list[DiscoveredPack]:
    return [entry for entry in entries if entry.distribution.startswith("dist-")]


def test_lists_one_entry_per_registered_pack(build: Callable[..., PackSource]) -> None:
    source = build(FakeDist("dist-good", "1.2.3", "good", "port_good_mod", GOOD_MODULE, "GoodPack"))
    [entry] = _ours(source.discover())
    assert (entry.name, entry.distribution, entry.version) == ("good", "dist-good", "1.2.3")
    cls = entry.load()
    assert isinstance(cls, type) and cls.name == "good"  # type: ignore[attr-defined]


def test_broken_import_only_fails_on_load(build: Callable[..., PackSource]) -> None:
    source = build(FakeDist("dist-broken", "0.1.0", "broken", "port_broken_mod", "raise RuntimeError('boom')", "X"))
    [entry] = _ours(source.discover())
    with pytest.raises(RuntimeError, match="boom"):
        entry.load()


def test_two_distributions_with_the_same_name_are_both_listed(build: Callable[..., PackSource]) -> None:
    source = build(
        FakeDist("dist-a", "0.1.0", "dup", "port_dup_a", GOOD_MODULE, "GoodPack"),
        FakeDist("dist-b", "0.1.0", "dup", "port_dup_b", GOOD_MODULE, "GoodPack"),
    )
    entries = _ours(source.discover())
    assert [(e.name, e.distribution) for e in entries] == [("dup", "dist-a"), ("dup", "dist-b")]
