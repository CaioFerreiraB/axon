from __future__ import annotations

import importlib.metadata

import ai_core_contracts


def test_version_constant_matches_distribution_metadata() -> None:
    assert ai_core_contracts.__version__ == importlib.metadata.version("ai-core-contracts")
