"""Corte seco do renome: só o nome novo existe (FR-022, US6 cenário 1; ADR-037, research R27; T071)."""

from __future__ import annotations

import importlib.metadata
import importlib.util

import axon_ai_contracts


def test_old_import_does_not_exist() -> None:
    assert importlib.util.find_spec("ai_core_contracts") is None


def test_distribution_and_import_carry_the_new_name_and_version() -> None:
    assert importlib.metadata.version("axon-ai-contracts") == axon_ai_contracts.__version__ == "0.2.0"
