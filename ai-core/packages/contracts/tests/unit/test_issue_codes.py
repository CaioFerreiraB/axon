"""Todo código emitido está em ISSUE_CODES, e todo `code=` é literal (T023)."""

from __future__ import annotations

import ast
from pathlib import Path

import axon_ai_contracts
from axon_ai_contracts.testing import ISSUE_CODES

PACKAGE_DIR = Path(axon_ai_contracts.__file__).resolve().parent
SOURCES = [PACKAGE_DIR / "declaration.py", *sorted((PACKAGE_DIR / "testing").glob("*.py"))]


def _issue_calls() -> list[tuple[str, int, ast.expr | None]]:
    calls: list[tuple[str, int, ast.expr | None]] = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ContractIssue":
                code = next((keyword.value for keyword in node.keywords if keyword.arg == "code"), None)
                calls.append((path.name, node.lineno, code))
    return calls


def test_every_code_argument_is_a_literal() -> None:
    offenders = [
        f"{name}:{line}"
        for name, line, code in _issue_calls()
        if not (isinstance(code, ast.Constant) and isinstance(code.value, str))
    ]
    assert not offenders, "ContractIssue sem code= literal: " + ", ".join(offenders)


def test_every_emitted_code_is_registered() -> None:
    emitted = {
        code.value for _, _, code in _issue_calls() if isinstance(code, ast.Constant) and isinstance(code.value, str)
    }
    assert emitted, "nenhum código encontrado"
    assert emitted <= ISSUE_CODES, sorted(emitted - ISSUE_CODES)
