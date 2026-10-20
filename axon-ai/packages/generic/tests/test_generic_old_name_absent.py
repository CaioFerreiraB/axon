"""Corte seco do renome: só o nome novo existe (spec 010 FR-009, US3 cenário 1; ADR-037, research R26; T031).

O nome do arquivo não é `test_no_old_name.py`: o pytest do workspace coleta os testes por nome de arquivo, e esse já
existe na suíte dos contratos.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util

import pytest


def test_old_import_does_not_exist() -> None:
    assert importlib.util.find_spec("ai_generic") is None


def test_old_distribution_is_not_installed() -> None:
    with pytest.raises(importlib.metadata.PackageNotFoundError):
        importlib.metadata.distribution("ai-generic")
