"""T072 — corte seco do nome do core (FR-022; ADR-037, item 3): não existe módulo com o nome antigo."""

from __future__ import annotations

import importlib.util


def test_o_modulo_antigo_nao_existe() -> None:
    assert importlib.util.find_spec("ai_core") is None
    assert importlib.util.find_spec("axon_ai") is not None
