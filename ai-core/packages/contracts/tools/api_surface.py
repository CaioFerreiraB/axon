"""Snapshot e diff da superfície pública de axon-ai-contracts (FR-020, SC-004; compatibility.md §7 a §9).

Uso, a partir de `ai-core/`:

    uv run python packages/contracts/tools/api_surface.py dump [--package NOME] [--output ARQUIVO]
    uv run python packages/contracts/tools/api_surface.py diff ANTIGO NOVO --old-version X --new-version Y

`dump` introspecta o pacote instalado; `diff` classifica as mudanças, calcula o bump exigido pela política (ADR-014) e
sai com código 1 se o bump declarado for menor ou se um símbolo for removido sem ter sido depreciado antes. Os módulos
são comparados pelo nome relativo à raiz do import; uma raiz ou distribuição renomeada é uma mudança breaking só
(FR-025, ADR-037).
Anotações entram como texto: todo módulo dos contratos usa `from __future__ import annotations`.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import importlib.metadata
import inspect
import json
import re
import sys
import typing
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import typing_extensions

PACKAGE = "axon_ai_contracts"
EXCLUDED = frozenset({"__version__"})
SET_CONSTANTS = frozenset({"ISSUE_CODES"})
_QUALIFIER_RE = re.compile(r"^(?:typing_extensions\.|typing\.)?(Required|NotRequired|ReadOnly)\[(.*)\]$", re.S)
_BUMP_ORDER = {"none": 0, "patch": 1, "minor": 2, "major": 3}

type Snapshot = dict[str, Any]
type ChangeKind = Literal["additive", "breaking"]


# ---------------------------------------------------------------------------------------------------------- dump


def _annotation_text(annotation: object) -> str | None:
    if annotation is inspect.Parameter.empty or annotation is None:
        return None
    if isinstance(annotation, str):
        return annotation
    forward = getattr(annotation, "__forward_arg__", None)
    if isinstance(forward, str):
        return forward
    return _type_repr(annotation)


def _type_repr(annotation: object) -> str:
    if isinstance(annotation, type):
        return annotation.__qualname__
    return repr(annotation)


def stable_repr(value: object) -> str:
    """`repr` que não depende da ordem de hash: conjuntos e mapeamentos saem ordenados."""
    if isinstance(value, frozenset | set):
        if not value:
            return f"{type(value).__name__}()"
        return f"{type(value).__name__}({{{', '.join(sorted(stable_repr(item) for item in value))}}})"
    if isinstance(value, MappingProxyType):
        return f"mappingproxy({stable_repr(dict(value))})"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda item: repr(item[0]))
        return "{" + ", ".join(f"{stable_repr(key)}: {stable_repr(item)}" for key, item in items) + "}"
    if isinstance(value, tuple):
        inner = ", ".join(stable_repr(item) for item in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, list):
        return "[" + ", ".join(stable_repr(item) for item in value) + "]"
    return repr(value)


def _signature(func: Callable[..., object]) -> dict[str, Any]:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return {"parameters": None, "return": None}
    parameters = [
        {
            "name": parameter.name,
            "kind": parameter.kind.name,
            "annotation": _annotation_text(parameter.annotation),
            "default": None if parameter.default is inspect.Parameter.empty else stable_repr(parameter.default),
            "has_default": parameter.default is not inspect.Parameter.empty,
        }
        for parameter in signature.parameters.values()
    ]
    return {"parameters": parameters, "return": _annotation_text(signature.return_annotation)}


def _callable_info(func: Callable[..., object]) -> dict[str, Any]:
    overloads = [_signature(overload) for overload in typing.get_overloads(func)]
    return {"async": inspect.iscoroutinefunction(func), **_signature(func), "overloads": overloads}


def _methods(cls: type) -> dict[str, Any]:
    methods: dict[str, Any] = {}
    for name, attribute in sorted(vars(cls).items()):
        if name.startswith("_"):
            continue
        if isinstance(attribute, property):
            annotations = getattr(attribute.fget, "__annotations__", {})
            methods[name] = {"member": "property", "annotation": _annotation_text(annotations.get("return"))}
        elif isinstance(attribute, classmethod | staticmethod):
            member = "classmethod" if isinstance(attribute, classmethod) else "staticmethod"
            methods[name] = {"member": member, **_callable_info(attribute.__func__)}
        elif inspect.isfunction(attribute):
            methods[name] = {"member": "method", **_callable_info(attribute)}
    return methods


def _protocol_members(protocol: type, defaults: type | None) -> dict[str, Any]:
    annotations = getattr(protocol, "__annotations__", {})
    members: dict[str, Any] = {}
    for name in sorted(typing_extensions.get_protocol_members(protocol)):
        in_base = defaults is not None and name in vars(defaults)
        attribute = vars(protocol).get(name)
        if inspect.isfunction(attribute):
            members[name] = {"member": "method", "default_in_base": in_base, **_callable_info(attribute)}
        else:
            members[name] = {
                "member": "attribute",
                "default_in_base": in_base,
                "annotation": _annotation_text(annotations.get(name)),
            }
    return members


def _typeddict_keys(typed_dict: type) -> dict[str, Any]:
    """Obrigatoriedade e ReadOnly lidos do texto da anotação: com PEP 563, `__required_keys__` sai errado."""
    total = bool(getattr(typed_dict, "__total__", True))
    keys: dict[str, Any] = {}
    for name, annotation in getattr(typed_dict, "__annotations__", {}).items():
        text = _annotation_text(annotation) or ""
        required, readonly = total, False
        while match := _QUALIFIER_RE.match(text.strip()):
            qualifier, text = match.group(1), match.group(2)
            if qualifier == "Required":
                required = True
            elif qualifier == "NotRequired":
                required = False
            else:
                readonly = True
        keys[name] = {"annotation": text.strip(), "required": required, "readonly": readonly}
    return dict(sorted(keys.items()))


def _fields(cls: type) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        if field.default is not dataclasses.MISSING:
            required, default = False, stable_repr(field.default)
        elif field.default_factory is not dataclasses.MISSING:
            required, default = False, stable_repr(field.default_factory())
        else:
            required, default = True, None
        fields[field.name] = {
            "annotation": _annotation_text(field.type),
            "required": required,
            "default": default,
            "kw_only": bool(field.kw_only),
        }
    return fields


def describe(obj: object, *, name: str = "", defaults: type | None = None) -> dict[str, Any]:
    """Descrição canônica de um símbolo público (compatibility.md §9)."""
    info: dict[str, Any] = {"deprecated_since": getattr(obj, "__contract_deprecated_since__", None)}
    if isinstance(obj, typing.TypeAliasType):
        info.update(kind="type_alias", value=_type_repr(obj.__value__))
    elif typing_extensions.is_typeddict(obj):
        info.update(kind="typeddict", total=bool(getattr(obj, "__total__", True)), keys=_typeddict_keys(obj))  # type: ignore[arg-type]
    elif isinstance(obj, type) and getattr(obj, "_is_protocol", False):
        info.update(kind="protocol", members=_protocol_members(obj, defaults))
    elif isinstance(obj, type) and dataclasses.is_dataclass(obj):
        info.update(kind="dataclass", fields=_fields(obj), methods=_methods(obj))
    elif isinstance(obj, type):
        info.update(kind="class", bases=[base.__qualname__ for base in obj.__bases__], methods=_methods(obj))
    elif callable(obj):
        info.update(kind="function", **_callable_info(obj))
    elif name in SET_CONSTANTS and isinstance(obj, frozenset | set):
        info.update(kind="constant", value=sorted(str(item) for item in obj))
    else:
        info.update(kind="constant", value=stable_repr(obj))
    return info


def _distribution_of(package: str) -> str:
    """Nome da distribuição instalada do pacote. Editável (o workspace), não há `top_level`: vale o nome derivado."""
    names = importlib.metadata.packages_distributions().get(package)
    if names:
        return names[0]
    try:
        return str(importlib.metadata.distribution(package.replace("_", "-")).metadata["Name"])
    except importlib.metadata.PackageNotFoundError:
        return package


def dump(package: str = PACKAGE) -> Snapshot:
    root = importlib.import_module(package)
    defaults = getattr(root, "PackBase", None)
    snapshot: Snapshot = {
        "distribution": _distribution_of(package),
        "package": package,
        "version": root.__version__,
        "modules": {},
    }
    for module_name in (package, f"{package}.testing"):
        module = importlib.import_module(module_name)
        symbols: dict[str, Any] = {}
        for name in sorted(set(module.__all__) - EXCLUDED):
            obj = getattr(module, name)
            symbols[name] = describe(obj, name=name, defaults=defaults if name == "AgentPack" else None)
        snapshot["modules"][module_name] = symbols
    return snapshot


# ---------------------------------------------------------------------------------------------------------- diff


@dataclass(frozen=True, slots=True)
class Change:
    kind: ChangeKind
    symbol: str
    detail: str
    removed_without_deprecation: bool = False


@dataclass(frozen=True, slots=True)
class Verdict:
    changes: tuple[Change, ...]
    required: str
    declared: str
    undeprecated_removals: tuple[str, ...]

    @property
    def failed(self) -> bool:
        return _BUMP_ORDER[self.declared] < _BUMP_ORDER[self.required] or bool(self.undeprecated_removals)


def _compare_parameters(old: list[dict[str, Any]] | None, new: list[dict[str, Any]] | None) -> ChangeKind | None:
    if old == new:
        return None
    if old is None or new is None:
        return "breaking"
    keyword_only = "KEYWORD_ONLY"
    if [p for p in old if p["kind"] != keyword_only] != [p for p in new if p["kind"] != keyword_only]:
        return "breaking"
    old_keywords = {p["name"]: p for p in old if p["kind"] == keyword_only}
    new_keywords = {p["name"]: p for p in new if p["kind"] == keyword_only}
    if any(new_keywords.get(name) != parameter for name, parameter in old_keywords.items()):
        return "breaking"
    extras = [parameter for name, parameter in new_keywords.items() if name not in old_keywords]
    return "additive" if all(parameter["has_default"] for parameter in extras) else "breaking"


def _compare_callable(symbol: str, old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    if old.get("async") != new.get("async"):
        return [Change("breaking", symbol, "async alterado")]
    if old.get("return") != new.get("return"):
        return [Change("breaking", symbol, "tipo de retorno alterado")]
    if old.get("overloads", []) != new.get("overloads", []):
        return [Change("breaking", symbol, "overloads alterados")]
    kind = _compare_parameters(old.get("parameters"), new.get("parameters"))
    if kind == "breaking":
        return [Change("breaking", symbol, "parâmetros alterados")]
    if kind == "additive":
        return [Change("additive", symbol, "parâmetro novo opcional e só-nome")]
    return []


def _compare_member(symbol: str, old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    if old.get("member") != new.get("member"):
        return [Change("breaking", symbol, "tipo do membro alterado")]
    if old.get("default_in_base") and not new.get("default_in_base"):
        return [Change("breaking", symbol, "PackBase deixou de fornecer default")]
    if old.get("member") in ("attribute", "property"):
        if old.get("annotation") != new.get("annotation"):
            return [Change("breaking", symbol, "anotação alterada")]
        return []
    return _compare_callable(symbol, old, new)


def _compare_members(symbol: str, old: dict[str, Any], new: dict[str, Any], *, protocol: bool) -> list[Change]:
    changes: list[Change] = []
    for name in sorted(set(old) | set(new)):
        member = f"{symbol}.{name}"
        if name not in new:
            changes.append(Change("breaking", member, "membro removido"))
        elif name not in old:
            additive = not protocol or bool(new[name].get("default_in_base"))
            detail = "membro novo" if additive else "membro novo em Protocol, sem default em PackBase"
            changes.append(Change("additive" if additive else "breaking", member, detail))
        else:
            changes.extend(_compare_member(member, old[name], new[name]))
    return changes


def _compare_fields(symbol: str, old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    changes: list[Change] = []
    for name in sorted(set(old) | set(new)):
        field = f"{symbol}.{name}"
        if name not in new:
            changes.append(Change("breaking", field, "campo removido"))
        elif name not in old:
            required = bool(new[name]["required"])
            detail = "campo novo sem default" if required else "campo novo com default"
            changes.append(Change("breaking" if required else "additive", field, detail))
        else:
            before, after = old[name], new[name]
            if before["annotation"] != after["annotation"]:
                changes.append(Change("breaking", field, "tipo do campo alterado"))
            elif not before["required"] and after["required"]:
                changes.append(Change("breaking", field, "campo perdeu o default"))
            elif not before["required"] and before["default"] != after["default"]:
                changes.append(Change("breaking", field, "default alterado"))
            elif before["kw_only"] != after["kw_only"]:
                changes.append(Change("breaking", field, "kw_only alterado"))
            elif before["required"] and not after["required"]:
                changes.append(Change("additive", field, "campo ganhou default"))
    return changes


def _compare_keys(symbol: str, old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    changes: list[Change] = []
    for name in sorted(set(old) | set(new)):
        key = f"{symbol}[{name!r}]"
        if name not in new:
            changes.append(Change("breaking", key, "chave removida"))
        elif name not in old:
            required = bool(new[name]["required"])
            detail = "chave nova obrigatória" if required else "chave nova opcional"
            changes.append(Change("breaking" if required else "additive", key, detail))
        elif old[name] != new[name]:
            changes.append(Change("breaking", key, "tipo, obrigatoriedade ou ReadOnly alterados"))
    return changes


def _compare_symbol(symbol: str, name: str, old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    if old["kind"] != new["kind"]:
        return [Change("breaking", symbol, f"tipo do símbolo mudou: {old['kind']} → {new['kind']}")]
    changes: list[Change] = []
    if old.get("deprecated_since") != new.get("deprecated_since"):
        changes.append(Change("additive", symbol, "marca de depreciação alterada"))
    kind = old["kind"]
    if kind == "dataclass":
        changes.extend(_compare_fields(symbol, old["fields"], new["fields"]))
        changes.extend(_compare_members(symbol, old.get("methods", {}), new.get("methods", {}), protocol=False))
    elif kind == "class":
        if old.get("bases") != new.get("bases"):
            changes.append(Change("breaking", symbol, "classes base alteradas"))
        changes.extend(_compare_members(symbol, old.get("methods", {}), new.get("methods", {}), protocol=False))
    elif kind == "protocol":
        changes.extend(_compare_members(symbol, old["members"], new["members"], protocol=True))
    elif kind == "typeddict":
        changes.extend(_compare_keys(symbol, old["keys"], new["keys"]))
    elif kind == "function":
        changes.extend(_compare_callable(symbol, old, new))
    elif kind == "constant" and name in SET_CONSTANTS:
        before, after = set(old["value"]), set(new["value"])
        changes.extend(Change("breaking", f"{symbol}:{code}", "código removido") for code in sorted(before - after))
        changes.extend(Change("additive", f"{symbol}:{code}", "código novo") for code in sorted(after - before))
    elif old.get("value") != new.get("value"):
        changes.append(Change("breaking", symbol, "valor alterado"))
    return changes


def _rebased(value: Any, pattern: re.Pattern[str], package: str) -> Any:
    """Troca a raiz antiga pela nova nos textos (anotações, `repr` de aliases e defaults) de uma linha de base."""
    if isinstance(value, str):
        return pattern.sub(package, value)
    if isinstance(value, dict):
        return {key: _rebased(item, pattern, package) for key, item in value.items()}
    if isinstance(value, list):
        return [_rebased(item, pattern, package) for item in value]
    return value


def _relative_modules(snapshot: Snapshot) -> dict[str, dict[str, Any]]:
    """Módulos pelo nome relativo à raiz do import: `""` para a raiz, `".testing"` para o kit."""
    package = str(snapshot["package"])
    return {name[len(package) :]: symbols for name, symbols in snapshot["modules"].items()}


def classify(old: Snapshot, new: Snapshot) -> list[Change]:
    """Mudanças entre dois snapshots, classificadas pela tabela §7 de compatibility.md.

    Os símbolos aparecem com o nome do HEAD. O renome da distribuição ou da raiz é uma mudança breaking só, que não
    conta como remoção sem depreciação (§8; ADR-037).
    """
    changes: list[Change] = []
    if (old["distribution"], old["package"]) != (new["distribution"], new["package"]):
        detail = (
            f"distribuição renomeada: {old['distribution']} ({old['package']}) → "
            f"{new['distribution']} ({new['package']})"
        )
        changes.append(Change("breaking", str(new["package"]), detail))
        # Sem isso, todo tipo que cita a raiz no texto (`NativeHandler`, anotações) sairia como alterado.
        pattern = re.compile(rf"\b{re.escape(str(old['package']))}\b")
        old = {**old, "modules": _rebased(old["modules"], pattern, str(new["package"]))}
    old_modules, new_modules = _relative_modules(old), _relative_modules(new)
    for module in sorted(set(old_modules) | set(new_modules)):
        before: dict[str, Any] = old_modules.get(module, {})
        after: dict[str, Any] = new_modules.get(module, {})
        for name in sorted(set(before) | set(after)):
            symbol = f"{new['package']}{module}.{name}"
            if name not in after:
                undeprecated = before[name].get("deprecated_since") is None
                changes.append(Change("breaking", symbol, "símbolo removido", removed_without_deprecation=undeprecated))
            elif name not in before:
                changes.append(Change("additive", symbol, "símbolo novo"))
            else:
                changes.extend(_compare_symbol(symbol, name, before[name], after[name]))
    return changes


def evaluate(
    old: Snapshot, new: Snapshot, *, old_version: str | None = None, new_version: str | None = None
) -> Verdict:
    """Bump exigido versus declarado (compatibility.md §8). As versões saem dos snapshots, se não forem informadas."""
    from axon_ai_contracts.compat import declared_bump, required_bump

    previous = old_version or str(old["version"])
    current = new_version or str(new["version"])
    changes = classify(old, new)
    level: Literal["none", "additive", "breaking"] = "none"
    if any(change.kind == "breaking" for change in changes):
        level = "breaking"
    elif changes:
        level = "additive"
    return Verdict(
        changes=tuple(changes),
        required=required_bump(level, current=previous),
        declared=declared_bump(previous, current),
        undeprecated_removals=tuple(change.symbol for change in changes if change.removed_without_deprecation),
    )


# ---------------------------------------------------------------------------------------------------------- CLI


def _load(path: str) -> Snapshot:
    loaded: Snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot e diff da superfície pública de axon-ai-contracts.")
    commands = parser.add_subparsers(dest="command", required=True)
    dump_parser = commands.add_parser("dump", help="gera o snapshot do pacote instalado")
    dump_parser.add_argument("--package", default=PACKAGE, help=f"pacote introspectado (default: {PACKAGE})")
    dump_parser.add_argument("--output", help="arquivo de saída (default: stdout)")
    diff_parser = commands.add_parser("diff", help="classifica mudanças e confere o bump declarado")
    diff_parser.add_argument("old")
    diff_parser.add_argument("new")
    diff_parser.add_argument("--old-version")
    diff_parser.add_argument("--new-version")
    args = parser.parse_args(argv)

    if args.command == "dump":
        text = json.dumps(dump(args.package), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0

    verdict = evaluate(_load(args.old), _load(args.new), old_version=args.old_version, new_version=args.new_version)
    for change in verdict.changes:
        marker = " (removido sem depreciação prévia)" if change.removed_without_deprecation else ""
        print(f"[{change.kind}] {change.symbol}: {change.detail}{marker}")
    print(f"bump exigido: {verdict.required}; declarado: {verdict.declared}")
    if verdict.failed:
        if verdict.undeprecated_removals:
            print("FALHA: símbolo removido sem depreciação na série anterior (ADR-014)", file=sys.stderr)
        if _BUMP_ORDER[verdict.declared] < _BUMP_ORDER[verdict.required]:
            print("FALHA: bump declarado menor que o exigido (FR-020)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
