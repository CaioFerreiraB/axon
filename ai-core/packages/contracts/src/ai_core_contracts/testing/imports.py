"""Varredura AST dos imports de um pack: packs só importam os contratos (US1 cenário 3, SC-005).

A regra é pura sobre a árvore sintática; a leitura dos arquivos-fonte fica nesta borda do kit de testes.
"""

from __future__ import annotations

import ast
import importlib.util
from collections.abc import Sequence
from pathlib import Path

from ai_core_contracts.declaration import ContractIssue

DEFAULT_FORBIDDEN: tuple[str, ...] = ("ai_core", "ai_generic")


def check_imports(package: str, *, forbidden: Sequence[str] = DEFAULT_FORBIDDEN) -> tuple[ContractIssue, ...]:
    """Aponta, com arquivo e linha, todo import absoluto de um módulo proibido.

    O próprio pacote varrido nunca é proibido (o `ai_generic` pode importar a si mesmo). Um módulo solto é varrido
    como um arquivo só. Levanta `ModuleNotFoundError` se o pacote não for encontrado.
    """
    top_level = package.split(".")[0]
    denied = tuple(name for name in forbidden if name != top_level)
    issues: list[ContractIssue] = []
    for root, path in _source_files(package):
        relative = path.relative_to(root).as_posix()
        for line, module in _absolute_imports(path):
            if any(module == name or module.startswith(f"{name}.") for name in denied):
                issues.append(
                    ContractIssue(
                        code="imports.forbidden",
                        message=f"import proibido de {module!r} em {relative}:{line}; packs importam só os contratos",
                        subject=f"file:{relative}:{line}",
                    )
                )
    return tuple(issues)


def _source_files(package: str) -> list[tuple[Path, Path]]:
    spec = importlib.util.find_spec(package)
    if spec is None:
        raise ModuleNotFoundError(f"pacote não encontrado: {package!r}")
    if spec.submodule_search_locations:
        files: list[tuple[Path, Path]] = []
        for location in spec.submodule_search_locations:
            base = Path(location)
            files.extend((base.parent, path) for path in sorted(base.rglob("*.py")) if "__pycache__" not in path.parts)
        return files
    if spec.origin and spec.origin.endswith(".py"):
        origin = Path(spec.origin)
        return [(origin.parent, origin)]
    return []


def _absolute_imports(path: Path) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return sorted(found)
