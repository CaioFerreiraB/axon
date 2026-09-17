"""Superfície pública exata de `ai_core.packs.api` e suas dependências (contracts/pack-runtime-api.md; T030)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import ai_core.packs.api as api

SEAM_API = {
    "Composition",
    "CompositionError",
    "PackCapabilities",
    "PackConfigError",
    "PackEntry",
    "PackHookError",
    "PackHooks",
    "PackRegistry",
    "PackStatus",
    "RetrieverCapability",
    "Slices",
    "ValidationOutcome",
    "ValidatorRun",
}
IMPORTED_FROM_CONTRACTS = {"Citation", "JSONValue", "TurnView", "ValidationResult"}


def test_public_names_are_exactly_the_documented_ones() -> None:
    public = {name for name in vars(api) if not name.startswith("_")}
    stdlib_helpers = {"annotations", "dataclass", "StrEnum", "Literal", "Protocol", "Mapping", "Sequence"}
    assert public - stdlib_helpers - IMPORTED_FROM_CONTRACTS == SEAM_API


def test_api_imports_only_stdlib_and_contracts() -> None:
    tree = ast.parse(Path(api.__file__).read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= set(sys.stdlib_module_names) | {"ai_core_contracts"}, roots


def test_no_install_operation_is_exposed() -> None:
    """FR-014: não existe instalação de pack em runtime — nem no seam, nem no registry."""
    members = {
        name for protocol in (api.PackRegistry, api.PackHooks) for name in vars(protocol) if not name.startswith("_")
    }
    assert members == {"entries", "entry", "compose", "system_prompts", "prepare", "validate"}
    assert not any("install" in name for name in members)
