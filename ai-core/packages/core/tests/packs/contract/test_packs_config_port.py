"""Conformidade da porta PackConfigSource: memória e packs.yaml (contracts/ports.md, packs-yaml.md; T009)."""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from ai_core.packs.adapters.config_yaml import YamlPackConfigSource
from ai_core.packs.adapters.memory import InMemoryPackConfigSource
from ai_core.packs.api import PackConfigError
from ai_core.packs.ports import PackConfigSource, PackSettings

YAML = """
packs:
  good:
    enabled: true
    config:
      collection: docs
      limits: {top_k: 3}
  quiet:
    config: {collection: other}
  bare: {}
"""

MEMORY = {
    "good": PackSettings(enabled=True, config={"collection": "docs", "limits": {"top_k": 3}}),
    "quiet": PackSettings(config={"collection": "other"}),
    "bare": PackSettings(),
}


@pytest.fixture(params=["memory", "yaml"])
def source(request: pytest.FixtureRequest, tmp_path: Path) -> PackConfigSource:
    if request.param == "memory":
        return InMemoryPackConfigSource(MEMORY)
    path = tmp_path / "packs.yaml"
    path.write_text(textwrap.dedent(YAML), encoding="utf-8")
    return YamlPackConfigSource(path)


def test_settings(source: PackConfigSource) -> None:
    settings = source.load()
    assert set(settings) == {"good", "quiet", "bare"}
    assert settings["good"].enabled is True
    assert settings["good"].config == {"collection": "docs", "limits": {"top_k": 3}}


def test_absent_pack_is_not_listed(source: PackConfigSource) -> None:
    assert "ausente" not in source.load()


def test_defaults(source: PackConfigSource) -> None:
    settings = source.load()
    assert settings["quiet"].enabled is False
    assert settings["bare"].enabled is False and settings["bare"].config == {}


def _yaml(tmp_path: Path, text: str) -> Callable[[], object]:
    path = tmp_path / "packs.yaml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return YamlPackConfigSource(path).load


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("outra: 1\n", "packs"),
        ("packs: [a, b]\n", "packs"),
        ("packs:\n  good: [1]\n", "packs.good"),
        ("packs:\n  good: {enabled: true, extra: 1}\n", "packs.good.extra"),
        ("packs:\n  good: {enabled: 'sim'}\n", "packs.good.enabled"),
        ("packs:\n  good: {config: [1, 2]}\n", "packs.good.config"),
        ("packs:\n  good: {config: {quando: 2026-01-01}}\n", "packs.good.config"),
        ("packs: {good: {enabled: true}\n", "YAML inválido"),
    ],
)
def test_yaml_violations(tmp_path: Path, text: str, fragment: str) -> None:
    with pytest.raises(PackConfigError, match=fragment.replace(".", r"\.")):
        _yaml(tmp_path, text)()


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PackConfigError, match="não encontrado"):
        YamlPackConfigSource(tmp_path / "nao-existe.yaml").load()


def test_empty_packs_section(tmp_path: Path) -> None:
    assert _yaml(tmp_path, "packs:\n")() == {}
