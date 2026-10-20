"""Fronteira da distribuição: só stdlib + typing_extensions, e nada de I/O no runtime (FR-001, FR-017, research R20)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import axon_ai_contracts

PACKAGE_DIR = Path(axon_ai_contracts.__file__).resolve().parent
ALLOWED_ROOTS = set(sys.stdlib_module_names) | {"typing_extensions", "axon_ai_contracts"}
RUNTIME_DENYLIST = {
    "os",
    "io",
    "pathlib",
    "socket",
    "subprocess",
    "shutil",
    "urllib",
    "http",
    "time",
    "random",
    "secrets",
    "asyncio",
    "importlib.metadata",
}


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
            if node.module == "importlib":
                found.extend((node.lineno, f"importlib.{alias.name}") for alias in node.names)
    return found


def _python_files() -> list[Path]:
    return sorted(PACKAGE_DIR.rglob("*.py"))


def _is_runtime(path: Path) -> bool:
    return "testing" not in path.relative_to(PACKAGE_DIR).parts


def test_only_stdlib_and_typing_extensions() -> None:
    violations = [
        f"{path.relative_to(PACKAGE_DIR)}:{line}: {module}"
        for path in _python_files()
        for line, module in _imports(path)
        if module.split(".")[0] not in ALLOWED_ROOTS
    ]
    assert not violations, "imports fora da stdlib/typing_extensions:\n" + "\n".join(violations)


def test_runtime_modules_do_no_io() -> None:
    def denied(module: str) -> bool:
        return any(module == name or module.startswith(f"{name}.") for name in RUNTIME_DENYLIST)

    violations = [
        f"{path.relative_to(PACKAGE_DIR)}:{line}: {module}"
        for path in _python_files()
        if _is_runtime(path)
        for line, module in _imports(path)
        if denied(module)
    ]
    assert not violations, "módulos de runtime importando I/O, relógio ou aleatoriedade:\n" + "\n".join(violations)


def test_importing_contracts_does_not_load_the_testing_kit() -> None:
    code = "import sys, axon_ai_contracts; print('axon_ai_contracts.testing' in sys.modules)"
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert completed.stdout.strip() == "False"
