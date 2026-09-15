"""Depreciação: aviso com versões de depreciação e de remoção (US3 cenário 3; T036)."""

from __future__ import annotations

import pytest

from ai_core_contracts import ContractDeprecationWarning, contract_deprecated, removal_version


@contract_deprecated(since="0.1.0")
def old_function() -> int:
    return 1


@contract_deprecated(since="0.1.0", use_instead="new_function")
def replaced_function() -> int:
    return 2


@contract_deprecated(since="0.1.2")
class OldThing:
    pass


def test_function_warns_with_since_and_removal() -> None:
    with pytest.warns(ContractDeprecationWarning) as record:
        assert old_function() == 1
    assert (
        str(record[0].message) == "old_function está depreciado desde ai-core-contracts 0.1.0 e será removido em 0.2.0"
    )


def test_use_instead_is_appended() -> None:
    with pytest.warns(ContractDeprecationWarning, match="; use new_function$"):
        replaced_function()


def test_class_warns_on_instantiation() -> None:
    with pytest.warns(ContractDeprecationWarning, match="OldThing está depreciado desde ai-core-contracts 0.1.2"):
        OldThing()


def test_marker_attribute_for_surface_snapshot() -> None:
    assert old_function.__contract_deprecated_since__ == "0.1.0"  # type: ignore[attr-defined]
    assert OldThing.__contract_deprecated_since__ == "0.1.2"  # type: ignore[attr-defined]


def test_is_a_deprecation_warning() -> None:
    assert issubclass(ContractDeprecationWarning, DeprecationWarning)


@pytest.mark.parametrize(
    ("since", "removal"),
    [("0.1.3", "0.2.0"), ("0.4", "0.5.0"), ("1.4", "2.0.0"), ("2.0.1", "3.0.0")],
)
def test_removal_version(since: str, removal: str) -> None:
    assert removal_version(since) == removal
