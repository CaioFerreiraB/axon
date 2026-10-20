"""Carrega `tools/api_surface.py` (fora da distribuição) como módulo para os testes."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOOL_PATH = Path(__file__).resolve().parents[2] / "tools" / "api_surface.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("api_surface", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["api_surface"] = module
    spec.loader.exec_module(module)
    return module


API_SURFACE = _load()


@pytest.fixture
def api_surface() -> ModuleType:
    return API_SURFACE
