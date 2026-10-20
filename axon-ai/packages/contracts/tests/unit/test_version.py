from __future__ import annotations

import importlib.metadata

import axon_ai_contracts


def test_version_constant_matches_distribution_metadata() -> None:
    assert axon_ai_contracts.__version__ == importlib.metadata.version("axon-ai-contracts")
