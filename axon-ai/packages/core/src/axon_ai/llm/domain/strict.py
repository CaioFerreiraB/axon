"""Subconjunto estrito da OpenAI: conversão do esquema de saída e a inversa no conteúdo (FR-005; ADR-023; R27, R28).

O modo estrito da OpenAI exige raiz objeto (sem `anyOf` na raiz), todo campo em `required` (o opcional se emula com
união com `null`) e `additionalProperties: false` em todo objeto, e não aceita `allOf`, `not` nem `if/then/else`. Na
ida, o esquema é convertido para esse subconjunto; na volta, a conversão é desfeita — quem chama recebe o conteúdo na
forma do esquema original. O que não tem equivalente estrito é recusado com o caminho do ponto (`$.properties.a`).

Puro: sem I/O, sem SDK. Quem aplica é o adapter (`adapters/remote.py`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from axon_ai_contracts import JSONValue

OPTIONAL_KEY: Final = "x-axon-optional"
"""Anotação interna do esquema anotado: as propriedades cuja anulabilidade a conversão introduziu. Nunca vai ao
provider."""

WRAPPER_KEY: Final = "value"

_ANNOTATIONS: Final = frozenset({"default", "examples", "title", "$comment", "deprecated", "readOnly", "writeOnly"})
_UNSUPPORTED: Final = frozenset(
    {
        "allOf",
        "not",
        "if",
        "then",
        "else",
        "dependentRequired",
        "dependentSchemas",
        "patternProperties",
        "unevaluatedProperties",
        "unevaluatedItems",
        "propertyNames",
        "minProperties",
        "maxProperties",
    }
)
_DEFINITIONS: Final = ("$defs", "definitions")
_TYPED: Final = ("type", "enum", "const", "anyOf", "$ref")


class StrictSchemaError(ValueError):
    """O esquema tem uma construção sem equivalente no modo estrito; `path` aponta onde."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


@dataclass(frozen=True, slots=True)
class StrictPlan:
    """O esquema de envio (`wire`), o anotado para a volta (`annotated`) e se a raiz foi embrulhada em `value`."""

    wire: dict[str, Any]
    annotated: dict[str, Any]
    wrapped: bool


def to_strict(schema: Mapping[str, JSONValue]) -> StrictPlan:
    """Converte para o subconjunto estrito, sem alterar o esquema recebido. Levanta `StrictSchemaError`."""
    annotated = _convert(schema, "$")
    wrapped = annotated.get("type") != "object"
    if wrapped:
        definitions: dict[str, Any] = {key: annotated.pop(key) for key in _DEFINITIONS if key in annotated}
        annotated = {
            "type": "object",
            "properties": {WRAPPER_KEY: annotated},
            "required": [WRAPPER_KEY],
            "additionalProperties": False,
            **definitions,
        }
    return StrictPlan(wire=_strip(annotated), annotated=annotated, wrapped=wrapped)


def from_strict(value: JSONValue, plan: StrictPlan) -> JSONValue:
    """Desfaz a conversão num valor gerado sob o esquema estrito. O que não casa volta como veio."""
    root = plan.annotated
    if not plan.wrapped:
        restored: JSONValue = _restore(value, root, root)
        return restored
    if not (isinstance(value, dict) and set(value) == {WRAPPER_KEY}):
        return value
    unwrapped: JSONValue = _restore(value[WRAPPER_KEY], root["properties"][WRAPPER_KEY], root)
    return unwrapped


# --- conversão ----------------------------------------------------------------------------------------------------


def _convert(node: object, path: str) -> dict[str, Any]:
    if not isinstance(node, Mapping):
        raise StrictSchemaError(path, "esquema precisa ser um objeto JSON")
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED:
            raise StrictSchemaError(path, f"`{key}` não tem equivalente no modo estrito")
        if key in _ANNOTATIONS:
            continue
        if key in ("anyOf", "oneOf"):
            if not isinstance(value, Sequence) or isinstance(value, str):
                raise StrictSchemaError(path, f"`{key}` precisa ser uma lista")
            out.setdefault("anyOf", []).extend(
                _convert(item, f"{path}.{key}[{index}]") for index, item in enumerate(value)
            )
        elif key == "properties" or key in _DEFINITIONS:
            if not isinstance(value, Mapping):
                raise StrictSchemaError(path, f"`{key}` precisa ser um objeto")
            out[key] = {name: _convert(item, f"{path}.{key}.{name}") for name, item in value.items()}
        elif key == "items":
            if not isinstance(value, Mapping):
                raise StrictSchemaError(path, "`items` em forma de lista não tem equivalente no modo estrito")
            out[key] = _convert(value, f"{path}.items")
        elif key == "additionalProperties":
            if value is not False:
                raise StrictSchemaError(path, "`additionalProperties` aberto não tem equivalente no modo estrito")
        else:
            out[key] = _plain(value)

    if "type" not in out and ("const" in out or "enum" in out):
        out["type"] = _inferred_type(out)
    if _is_object(out):
        _close_object(node, out, path)
    if not any(key in out for key in _TYPED):
        raise StrictSchemaError(path, "esquema sem tipo não tem equivalente no modo estrito")
    return out


def _inferred_type(schema: Mapping[str, Any]) -> str | list[str]:
    """O modo estrito exige `type` em todo nó, inclusive em `const` e `enum` (visto num 400 real da OpenAI)."""
    values = [schema["const"]] if "const" in schema else list(schema["enum"])
    kinds = list(dict.fromkeys(_json_type(value) for value in values))
    return kinds[0] if len(kinds) == 1 else kinds


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list | tuple):
        return "array"
    return "object"


def _is_object(schema: Mapping[str, Any]) -> bool:
    kind = schema.get("type")
    return kind == "object" or (isinstance(kind, list) and "object" in kind)


def _close_object(original: Mapping[str, Any], out: dict[str, Any], path: str) -> None:
    """Todo nome em `required`, `additionalProperties: false`, opcional anulável — anotando o que foi introduzido."""
    if "properties" not in out:
        if original.get("additionalProperties") is not False:
            raise StrictSchemaError(path, "objeto livre (sem `properties`) não tem equivalente no modo estrito")
        out["properties"] = {}
    required = set(out.get("required") or ())
    introduced: list[str] = []
    for name, sub in out["properties"].items():
        if name not in required and not _allows_null(sub):
            out["properties"][name] = _nullable(sub)
            introduced.append(name)
    out["required"] = list(out["properties"])
    out["additionalProperties"] = False
    if introduced:
        out[OPTIONAL_KEY] = introduced


def _allows_null(schema: Mapping[str, Any]) -> bool:
    kind = schema.get("type")
    if kind == "null" or (isinstance(kind, list) and "null" in kind):
        return True
    if "const" in schema:
        return schema["const"] is None
    if "enum" in schema and None in schema["enum"]:
        return kind is None
    return any(_allows_null(branch) for branch in schema.get("anyOf") or ())


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    if "const" in schema or "$ref" in schema:
        return {"anyOf": [schema, {"type": "null"}]}
    out = dict(schema)
    kind = out.get("type")
    if isinstance(kind, str):
        out["type"] = [kind, "null"]
    elif isinstance(kind, list):
        out["type"] = [*kind, "null"]
    elif "anyOf" in out:
        out["anyOf"] = [*out["anyOf"], {"type": "null"}]
    if "enum" in out and None not in out["enum"]:
        out["enum"] = [*out["enum"], None]
    return out


def _plain(value: object) -> Any:
    """Cópia em tipos simples (esquemas da 004 chegam congelados)."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def _strip(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _strip(value) for key, value in node.items() if key != OPTIONAL_KEY}
    if isinstance(node, list):
        return [_strip(item) for item in node]
    return node


# --- inversa ------------------------------------------------------------------------------------------------------


def _restore(value: Any, node: Mapping[str, Any], root: Mapping[str, Any]) -> Any:
    node = _deref(node, root)
    if "anyOf" in node:
        for branch in node["anyOf"]:
            resolved = _deref(branch, root)
            if _matches(value, resolved):
                return _restore(value, resolved, root)
        return value
    properties = node.get("properties")
    if isinstance(value, dict) and isinstance(properties, Mapping):
        introduced = set(node.get(OPTIONAL_KEY) or ())
        restored: dict[str, Any] = {}
        for key, item in value.items():
            if item is None and key in introduced:
                continue
            sub = properties.get(key)
            restored[key] = item if sub is None else _restore(item, sub, root)
        return restored
    items = node.get("items")
    if isinstance(value, list) and isinstance(items, Mapping):
        return [_restore(item, items, root) for item in value]
    return value


def _deref(node: Mapping[str, Any], root: Mapping[str, Any]) -> Mapping[str, Any]:
    reference = node.get("$ref")
    if not isinstance(reference, str) or not reference.startswith("#/"):
        return node
    target: Any = root
    for part in reference[2:].split("/"):
        if not isinstance(target, Mapping) or part not in target:
            return node
        target = target[part]
    return target if isinstance(target, Mapping) else node


_JSON_TYPES: Final = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _matches(value: Any, schema: Mapping[str, Any]) -> bool:
    """O valor cabe no ramo: tipo, `const`/`enum` e — num objeto estrito — exatamente as chaves do ramo."""
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    kinds = schema.get("type")
    if kinds is not None:
        allowed = [kinds] if isinstance(kinds, str) else list(kinds)
        if not any(_is_type(value, kind) for kind in allowed):
            return False
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        if not isinstance(value, dict) or set(value) != set(properties):
            return False
        return all(_matches(value[key], _shallow(sub)) for key, sub in properties.items())
    return True


def _shallow(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """Só o que decide o ramo sem descer mais: `const`, `enum` e tipo."""
    return {key: schema[key] for key in ("const", "enum", "type") if key in schema}


def _is_type(value: Any, kind: str) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    expected = _JSON_TYPES.get(kind)
    return expected is not None and isinstance(value, expected)
