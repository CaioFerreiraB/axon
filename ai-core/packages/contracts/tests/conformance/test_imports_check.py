"""Varredura de imports do pacote do pack (US1 cenário 3, SC-005; T017)."""

from __future__ import annotations

import importlib
import sys
import textwrap
from pathlib import Path

import pytest

from ai_core_contracts.testing import acheck_pack, check_imports

BAD_PACKAGE = """
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_core_contracts import PackBase, PackManifest

if TYPE_CHECKING:
    import ai_core.graph


def _nunca_chamada() -> None:
    from ai_generic import prompts


class BadPack(PackBase):
    name = "bad"
    contract_version = "0.1"

    def manifest(self) -> PackManifest:
        return PackManifest(name="bad", version="0.1.0")
"""


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    yield tmp_path
    for name in [module for module in sys.modules if module.split(".")[0] in {"badpkg", "cleanpkg", "solo"}]:
        del sys.modules[name]


def test_forbidden_imports_are_reported_with_file_and_line(sandbox: Path) -> None:
    _write(sandbox, "badpkg/__init__.py", BAD_PACKAGE)
    issues = check_imports("badpkg")
    assert [issue.code for issue in issues] == ["imports.forbidden", "imports.forbidden"]
    subjects = [issue.subject for issue in issues]
    assert subjects == ["file:badpkg/__init__.py:9", "file:badpkg/__init__.py:13"]
    assert "ai_core.graph" in issues[0].message
    assert "ai_generic" in issues[1].message


def test_clean_package_has_no_issues(sandbox: Path) -> None:
    _write(sandbox, "cleanpkg/__init__.py", "from ai_core_contracts import PackBase\nfrom . import sub\n")
    _write(sandbox, "cleanpkg/sub.py", "import json\n")
    assert check_imports("cleanpkg") == ()


def test_package_may_import_itself(sandbox: Path) -> None:
    _write(sandbox, "ai_generic_fake/__init__.py", "")
    issues = check_imports("ai_generic_fake", forbidden=("ai_core", "ai_generic_fake"))
    assert issues == ()


def test_single_module_is_scanned_as_one_file(sandbox: Path) -> None:
    _write(sandbox, "solo.py", "import ai_core\n")
    [issue] = check_imports("solo")
    assert issue.subject == "file:solo.py:1"


async def test_conformance_reports_forbidden_import(sandbox: Path) -> None:
    _write(sandbox, "badpkg/__init__.py", BAD_PACKAGE)
    module = importlib.import_module("badpkg")
    report = await acheck_pack(module.BadPack(), check_distribution=False)
    assert not report.ok
    assert {issue.code for issue in report.issues} == {"imports.forbidden"}
