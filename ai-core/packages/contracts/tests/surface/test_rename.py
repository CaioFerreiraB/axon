"""Renome da distribuição e da raiz do import na linha de base (FR-025, US6 cenário 4; research R30, T070)."""

from __future__ import annotations

from types import ModuleType
from typing import Any

OLD_PACKAGE, NEW_PACKAGE = "old_contracts", "axon_ai_contracts"
TURN_VIEW: dict[str, Any] = {"kind": "class", "deprecated_since": None, "bases": ["object"], "methods": {}}
HELPER: dict[str, Any] = {
    "kind": "function",
    "deprecated_since": None,
    "async": False,
    "parameters": [],
    "return": "str",
    "overloads": [],
}


def snapshot(distribution: str, package: str, version: str, *, helper: dict[str, Any] = HELPER) -> dict[str, Any]:
    return {
        "distribution": distribution,
        "package": package,
        "version": version,
        "modules": {package: {"TurnView": TURN_VIEW}, f"{package}.testing": {"turn_view": helper}},
    }


OLD = snapshot("old-contracts", OLD_PACKAGE, "0.1.3")
NEW = snapshot("axon-ai-contracts", NEW_PACKAGE, "0.2.0")


def test_rename_is_one_breaking_change_without_undeprecated_removals(api_surface: ModuleType) -> None:
    [change] = api_surface.classify(OLD, NEW)
    assert change.kind == "breaking"
    assert change.symbol == NEW_PACKAGE
    assert change.detail == (
        "distribuição renomeada: old-contracts (old_contracts) → axon-ai-contracts (axon_ai_contracts)"
    )
    assert not change.removed_without_deprecation


def test_rename_requires_minor(api_surface: ModuleType) -> None:
    accepted = api_surface.evaluate(OLD, NEW, old_version="0.1.3", new_version="0.2.0")
    assert (accepted.required, accepted.declared, accepted.failed) == ("minor", "minor", False)
    refused = api_surface.evaluate(OLD, NEW, old_version="0.1.3", new_version="0.1.4")
    assert (refused.required, refused.declared, refused.failed) == ("minor", "patch", True)
    assert refused.undeprecated_removals == ()


def test_symbols_are_still_compared_across_the_rename(api_surface: ModuleType) -> None:
    changed = snapshot("axon-ai-contracts", NEW_PACKAGE, "0.2.0", helper={**HELPER, "return": "int"})
    details = {(change.symbol, change.detail) for change in api_surface.classify(OLD, changed)}
    assert (f"{NEW_PACKAGE}.testing.turn_view", "tipo de retorno alterado") in details
    assert len(details) == 2


def test_symbol_removed_with_the_rename_still_needs_deprecation(api_surface: ModuleType) -> None:
    removed = snapshot("axon-ai-contracts", NEW_PACKAGE, "0.2.0")
    del removed["modules"][f"{NEW_PACKAGE}.testing"]["turn_view"]
    verdict = api_surface.evaluate(OLD, removed, old_version="0.1.3", new_version="0.2.0")
    assert verdict.undeprecated_removals == (f"{NEW_PACKAGE}.testing.turn_view",)
    assert verdict.failed


def test_root_in_annotations_is_rebased_before_comparing(api_surface: ModuleType) -> None:
    """O `repr` de um alias cita o módulo: `old_contracts.tools.X` e `axon_ai_contracts.tools.X` são o mesmo tipo."""
    alias = {"kind": "type_alias", "deprecated_since": None}
    old = snapshot("old-contracts", OLD_PACKAGE, "0.1.3")
    new = snapshot("axon-ai-contracts", NEW_PACKAGE, "0.2.0")
    old["modules"][OLD_PACKAGE]["Handler"] = {**alias, "value": "Callable[[old_contracts.tools.X], str]"}
    new["modules"][NEW_PACKAGE]["Handler"] = {**alias, "value": "Callable[[axon_ai_contracts.tools.X], str]"}
    old["modules"][OLD_PACKAGE]["Other"] = {**alias, "value": "old_contracts_extra.Y"}
    new["modules"][NEW_PACKAGE]["Other"] = {**alias, "value": "axon_ai_contracts_extra.Y"}
    symbols = [change.symbol for change in api_surface.classify(old, new)]
    assert symbols == [NEW_PACKAGE, f"{NEW_PACKAGE}.Other"]


def test_same_name_has_no_rename_change(api_surface: ModuleType) -> None:
    assert api_surface.classify(NEW, snapshot("axon-ai-contracts", NEW_PACKAGE, "0.2.1")) == []


def test_dump_records_package_and_distribution(api_surface: ModuleType) -> None:
    current = api_surface.dump()
    assert (current["distribution"], current["package"]) == ("axon-ai-contracts", NEW_PACKAGE)
    assert set(current["modules"]) == {NEW_PACKAGE, f"{NEW_PACKAGE}.testing"}
