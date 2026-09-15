"""Regra de compatibilidade: faixa derivada e mensagens exatas (US3 cenários 1 e 2; T034)."""

from __future__ import annotations

import pytest

from ai_core_contracts import InvalidSpecifier, InvalidVersion, check_compatibility, derive_range


@pytest.mark.parametrize(
    ("contract_version", "expected"),
    [("0.1", ">=0.1,<0.2"), ("0.1.3", ">=0.1.3,<0.2"), ("1.2", ">=1.2,<2"), ("1.2.3", ">=1.2.3,<2")],
)
def test_derived_range(contract_version: str, expected: str) -> None:
    assert str(derive_range(contract_version)) == expected


@pytest.mark.parametrize(
    ("installed", "requirement", "message"),
    [
        ("0.1.4", "0.1", None),
        ("0.1.4", "0.2", "requer ai-core-contracts>=0.2, instalado 0.1.4"),
        ("0.2.0", "0.1", "requer ai-core-contracts<0.2, instalado 0.2.0"),
        ("0.2.0rc1", "0.1", "requer ai-core-contracts<0.2, instalado 0.2.0rc1"),
        ("0.1.2", "0.1.3", "requer ai-core-contracts>=0.1.3, instalado 0.1.2"),
        ("1.4.0", ">=1.2,<2", None),
    ],
)
def test_compatibility_table(installed: str, requirement: str, message: str | None) -> None:
    result = check_compatibility(requirement, installed=installed)
    assert result.ok is (message is None)
    assert result.message == message


def test_future_major_is_incompatible() -> None:
    result = check_compatibility("1.0", installed="0.1.0")
    assert result.message == "requer ai-core-contracts>=1.0, instalado 0.1.0"


def test_explicit_range_is_accepted() -> None:
    assert check_compatibility(">=0.1,<0.2", installed="0.1.9").ok
    assert not check_compatibility("~=0.1.3", installed="0.1.2").ok


def test_malformed_requirement() -> None:
    with pytest.raises(InvalidVersion):
        check_compatibility("abc", installed="0.1.0")
    with pytest.raises(InvalidSpecifier):
        check_compatibility(">=abc", installed="0.1.0")
    with pytest.raises(InvalidVersion):
        check_compatibility("0.1", installed="v0.1")
