"""Dependência de axon-ai-contracts declarada pelo pack cabe na faixa derivada (FR-018; T037)."""

from __future__ import annotations

import pytest

from axon_ai_contracts.testing import check_contracts_requirement


def _codes(requirements: list[str], contract_version: str = "0.1") -> list[str]:
    return [issue.code for issue in check_contracts_requirement(requirements, contract_version)]


def test_missing_requirement() -> None:
    assert _codes(["outra-lib>=1"]) == ["distribution.missing_requirement"]
    assert _codes([]) == ["distribution.missing_requirement"]


def test_direct_reference() -> None:
    assert _codes(["axon-ai-contracts @ git+https://github.com/caio/axon-ai@contracts-v0.1.0"]) == [
        "distribution.direct_reference"
    ]


def test_unsupported_specifier() -> None:
    assert _codes(["axon-ai-contracts===0.1"]) == ["distribution.unsupported_specifier"]


@pytest.mark.parametrize("specifier", [">=0.1", "~=0.1", ">=0.0.5,<0.2", "", ">=0.1,<=0.2"])
def test_range_too_wide(specifier: str) -> None:
    [issue] = check_contracts_requirement([f"axon-ai-contracts{specifier}"], "0.1")
    assert issue.code == "distribution.range_too_wide"
    assert ">=0.1,<0.2" in issue.message


def test_range_disjoint() -> None:
    assert _codes(["axon-ai-contracts>=0.3,<0.4"]) == ["distribution.range_disjoint"]


@pytest.mark.parametrize(
    "requirement",
    [
        "axon-ai-contracts>=0.1,<0.2",
        "axon-ai-contracts<0.2,>=0.1",
        "axon-ai-contracts>=0.1.3,<0.2",
        "axon-ai-contracts~=0.1.3",
        "axon-ai-contracts==0.1.*",
        'axon_ai_contracts[x]>=0.1,<0.2 ; python_version >= "3.12"',
        "AXON.Ai_Contracts (>=0.1,<0.2)",
    ],
)
def test_requirement_within_derived_range(requirement: str) -> None:
    assert _codes([requirement]) == []


def test_extra_only_requirement_does_not_count() -> None:
    assert _codes(['axon-ai-contracts>=0.1,<0.2 ; extra == "dev"']) == ["distribution.missing_requirement"]


def test_narrower_contract_version() -> None:
    assert _codes(["axon-ai-contracts>=0.1,<0.2"], "0.1.3") == ["distribution.range_too_wide"]
    assert _codes(["axon-ai-contracts>=0.1.3,<0.2"], "0.1.3") == []


def test_old_distribution_name_is_not_the_contracts() -> None:
    """US6 cenário 3 (FR-023, R28): o nome antigo é uma dependência qualquer; a mensagem pede o novo."""
    [issue] = check_contracts_requirement(["ai-core-contracts>=0.1,<0.2"], "0.2")
    assert issue.code == "distribution.missing_requirement"
    assert issue.message.endswith("dependência de axon-ai-contracts; declare >=0.2,<0.3")


def test_only_the_new_name_is_checked_when_both_are_declared() -> None:
    assert _codes(["ai-core-contracts>=0.1", "axon-ai-contracts>=0.2,<0.3"], "0.2") == []
