"""Carga completa com entry points e packs.yaml reais (US1, teste independente; quickstart §3; T012)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from packs_testkit import GOOD_MODULE, FakeDistributions

from ai_core.packs.adapters.config_yaml import YamlPackConfigSource
from ai_core.packs.adapters.entry_points import EntryPointPackSource
from ai_core.packs.api import PackStatus
from ai_core.packs.service import PackRuntime


def _runtime(tmp_path: Path, fake: FakeDistributions, packs_yaml: str) -> PackRuntime:
    fake.add(
        "dist-good",
        version="2.0.1",
        entry_points={"good": "integration_good_mod:GoodPack"},
        modules={"integration_good_mod": GOOD_MODULE},
    )
    config = tmp_path / "packs.yaml"
    config.write_text(textwrap.dedent(packs_yaml), encoding="utf-8")
    runtime = PackRuntime(EntryPointPackSource(), YamlPackConfigSource(config))
    runtime.load()
    return runtime


def test_installed_and_enabled_pack_is_loaded(tmp_path: Path, fake_distributions: FakeDistributions) -> None:
    runtime = _runtime(
        tmp_path, fake_distributions, "packs:\n  good:\n    enabled: true\n    config: {collection: docs}\n"
    )
    entry = runtime.entry("good")
    assert entry is not None and entry.status is PackStatus.ENABLED
    assert (entry.version, entry.contract_version) == ("2.0.1", "0.1")
    assert entry.capabilities is not None and entry.capabilities.system_prompt


@pytest.mark.parametrize("packs_yaml", ["packs: {}\n", "packs:\n  good: {enabled: false}\n"])
def test_not_enabled_pack_is_disabled(tmp_path: Path, fake_distributions: FakeDistributions, packs_yaml: str) -> None:
    runtime = _runtime(tmp_path, fake_distributions, packs_yaml)
    entry = runtime.entry("good")
    assert entry is not None and entry.status is PackStatus.DISABLED
    import integration_good_mod  # type: ignore[import-not-found]

    assert integration_good_mod.GoodPack.created == 0


def test_config_violating_schema(tmp_path: Path, fake_distributions: FakeDistributions) -> None:
    runtime = _runtime(
        tmp_path, fake_distributions, "packs:\n  good:\n    enabled: true\n    config: {collection: 7}\n"
    )
    entry = runtime.entry("good")
    assert entry is not None and entry.status is PackStatus.ERROR
    assert entry.error is not None and entry.error.startswith("configuração inválida em 'collection':")
