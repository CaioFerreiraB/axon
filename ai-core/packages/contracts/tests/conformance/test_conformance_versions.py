"""Conformidade: depreciação capturada e dependência declarada do pack (FR-016, FR-018; T039)."""

from __future__ import annotations

from typing import Any

import pytest
from packs import GoodPack, make_pack

from axon_ai_contracts import contract_deprecated
from axon_ai_contracts.testing import check_pack
from axon_ai_contracts.testing import conformance as conformance_module


@contract_deprecated(since="0.1.0")
def legacy_helper() -> str:
    return "texto"


def test_deprecated_symbol_is_reported_as_warning() -> None:
    report = check_pack(make_pack(system_prompt=lambda self, ctx: legacy_helper()), check_distribution=False)
    assert report.ok
    [issue] = report.issues
    assert (issue.code, issue.severity) == ("deprecation.used", "warning")
    assert "desde axon-ai-contracts 0.1.0" in issue.message and "0.2.0" in issue.message


def test_distribution_requirement_is_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conformance_module, "find_distribution", lambda pack: "fake-pack")
    monkeypatch.setattr(conformance_module, "read_requirements", lambda distribution: ["axon-ai-contracts>=0.1"])
    report = check_pack(GoodPack())
    assert [issue.code for issue in report.issues] == ["distribution.range_too_wide"]


def test_distribution_step_can_be_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any) -> None:
        raise AssertionError("não deveria consultar a distribuição")

    monkeypatch.setattr(conformance_module, "find_distribution", fail)
    assert check_pack(GoodPack(), check_distribution=False).issues == ()


def test_distribution_not_found_is_a_warning() -> None:
    report = check_pack(GoodPack())
    assert report.ok
    assert [(issue.code, issue.severity) for issue in report.issues] == [("distribution.not_found", "warning")]
