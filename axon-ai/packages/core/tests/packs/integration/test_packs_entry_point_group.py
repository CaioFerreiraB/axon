"""O grupo de registro `axon.packs` e o corte seco do grupo antigo (US8 cenários 1 a 4; FR-023, FR-024; R54; T086)."""

from __future__ import annotations

import io

from packs_testkit import FakeDistributions

from axon_ai.packs.adapters.cli import check_command
from axon_ai.packs.adapters.entry_points import PACKS_GROUP, EntryPointPackSource
from axon_ai.packs.adapters.memory import InMemoryPackConfigSource
from axon_ai.packs.api import PackStatus
from axon_ai.packs.ports import PackSettings
from axon_ai.packs.service import PackRuntime

OLD_GROUP = "ai_core.packs"

PACK_MODULE = """
from axon_ai_contracts import PackBase, PackManifest


class Pack(PackBase):
    name = "{name}"
    contract_version = "0.2"

    def manifest(self):
        return PackManifest(name="{name}", version="0.1.0")
"""


def _install(fake: FakeDistributions, name: str, *, group: str = PACKS_GROUP) -> None:
    module = f"group_{name}_mod"
    fake.add(
        f"dist-{name}",
        entry_points={name: f"{module}:Pack"},
        modules={module: PACK_MODULE.format(name=name)},
        group=group,
    )


def _runtime(*enabled: str) -> PackRuntime:
    settings = {name: PackSettings(enabled=True) for name in enabled}
    runtime = PackRuntime(EntryPointPackSource(), InMemoryPackConfigSource(settings))
    runtime.load()
    return runtime


def test_the_group_is_axon_packs() -> None:
    assert PACKS_GROUP == "axon.packs"


def test_pack_in_the_new_group_is_discovered_and_loaded(fake_distributions: FakeDistributions) -> None:
    _install(fake_distributions, "novo")
    entry = _runtime("novo").entry("novo")
    assert entry is not None and entry.status is PackStatus.ENABLED, entry


def test_enabled_pack_only_in_the_old_group_is_not_installed(fake_distributions: FakeDistributions) -> None:
    _install(fake_distributions, "antigo", group=OLD_GROUP)
    _install(fake_distributions, "vizinho")
    runtime = _runtime("antigo", "vizinho")
    old = runtime.entry("antigo")
    assert old is not None and old.status is PackStatus.ERROR
    assert old.error == "não instalado"
    neighbour = runtime.entry("vizinho")
    assert neighbour is not None and neighbour.status is PackStatus.ENABLED


def test_packs_check_fails_naming_the_pack_left_in_the_old_group(fake_distributions: FakeDistributions) -> None:
    _install(fake_distributions, "antigo", group=OLD_GROUP)
    out = io.StringIO()
    assert check_command(_runtime("antigo"), out) == 1
    assert "antigo" in out.getvalue() and "não instalado" in out.getvalue()


def test_pack_only_in_the_old_group_and_not_enabled_is_not_listed(fake_distributions: FakeDistributions) -> None:
    _install(fake_distributions, "antigo", group=OLD_GROUP)
    assert "antigo" not in [entry.name for entry in _runtime().entries()]
