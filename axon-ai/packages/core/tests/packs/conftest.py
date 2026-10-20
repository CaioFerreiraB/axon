"""Fixtures dos testes do Pack Runtime; helpers ficam em `packs_testkit.py`."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from packs_testkit import FakeDistributions


@pytest.fixture
def fake_distributions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeDistributions]:
    monkeypatch.syspath_prepend(str(tmp_path))
    distributions = FakeDistributions(tmp_path)
    yield distributions
    for module in distributions.modules:
        sys.modules.pop(module, None)
    importlib.invalidate_caches()
