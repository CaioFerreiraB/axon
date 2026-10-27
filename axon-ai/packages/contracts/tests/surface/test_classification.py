"""Classificação de mudanças de superfície e bump exigido (compatibility.md §7 a §9, SC-004; T038).

Um teste por linha da tabela §7, com snapshots sintéticos no formato do `dump`, mais testes contra o pacote real.
"""

from __future__ import annotations

import copy
import importlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

MODULE = "axon_ai_contracts"
TOOL_PATH = Path(__file__).resolve().parents[2] / "tools" / "api_surface.py"


# ---------------------------------------------------------------- construtores de snapshot (formato §9)


def snapshot(symbols: dict[str, Any], *, version: str = "0.1.0") -> dict[str, Any]:
    return {"distribution": "axon-ai-contracts", "package": MODULE, "version": version, "modules": {MODULE: symbols}}


def param(name: str, kind: str = "POSITIONAL_OR_KEYWORD", annotation: str | None = "str", default: str | None = None):
    return {
        "name": name,
        "kind": kind,
        "annotation": annotation,
        "default": default,
        "has_default": default is not None,
    }


def function(*params: dict[str, Any], returns: str = "None", is_async: bool = False) -> dict[str, Any]:
    return {
        "kind": "function",
        "deprecated_since": None,
        "async": is_async,
        "parameters": list(params),
        "return": returns,
        "overloads": [],
    }


def method(*params: dict[str, Any], returns: str = "None", is_async: bool = False, in_base: bool = False):
    info = function(param("self", annotation=None), *params, returns=returns, is_async=is_async)
    del info["kind"], info["deprecated_since"]
    return {"member": "method", "default_in_base": in_base, **info}


def field(annotation: str = "str", *, default: str | None = None) -> dict[str, Any]:
    return {"annotation": annotation, "required": default is None, "default": default, "kw_only": True}


def dataclass_symbol(**fields: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "dataclass", "deprecated_since": None, "fields": fields, "methods": {}}


def protocol(**members: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "protocol", "deprecated_since": None, "members": members}


def key(annotation: str = "str", *, required: bool = True, readonly: bool = True) -> dict[str, Any]:
    return {"annotation": annotation, "required": required, "readonly": readonly}


def typeddict(**keys: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "typeddict", "deprecated_since": None, "total": True, "keys": keys}


def constant(value: Any) -> dict[str, Any]:
    return {"kind": "constant", "deprecated_since": None, "value": value}


def kinds(api_surface: ModuleType, old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    return [change.kind for change in api_surface.classify(snapshot(old), snapshot(new))]


BASE_DATACLASS = dataclass_symbol(name=field(), flag=field("bool", default="False"))


# ---------------------------------------------------------------- §7, linha a linha


def test_removed_symbol_is_breaking(api_surface: ModuleType) -> None:
    assert kinds(api_surface, {"A": BASE_DATACLASS}, {}) == ["breaking"]


def test_new_symbol_is_additive(api_surface: ModuleType) -> None:
    assert kinds(api_surface, {}, {"A": BASE_DATACLASS}) == ["additive"]


def test_kind_change_is_breaking(api_surface: ModuleType) -> None:
    assert "breaking" in kinds(api_surface, {"A": BASE_DATACLASS}, {"A": protocol()})


@pytest.mark.parametrize(
    "new_fields",
    [
        {"flag": field("bool", default="False")},  # campo removido
        {"nome": field(), "flag": field("bool", default="False")},  # campo renomeado
        {"name": field("int"), "flag": field("bool", default="False")},  # tipo alterado
        {"name": field(), "flag": field("bool", default="True")},  # default alterado
        {"name": field(), "flag": field("bool")},  # perdeu o default
    ],
)
def test_dataclass_field_breaking_changes(api_surface: ModuleType, new_fields: dict[str, Any]) -> None:
    assert "breaking" in kinds(api_surface, {"A": BASE_DATACLASS}, {"A": dataclass_symbol(**new_fields)})


def test_new_field_with_default_is_additive(api_surface: ModuleType) -> None:
    new = dataclass_symbol(name=field(), flag=field("bool", default="False"), extra=field("int", default="0"))
    assert kinds(api_surface, {"A": BASE_DATACLASS}, {"A": new}) == ["additive"]


def test_new_field_without_default_is_breaking(api_surface: ModuleType) -> None:
    new = dataclass_symbol(name=field(), flag=field("bool", default="False"), extra=field("int"))
    assert kinds(api_surface, {"A": BASE_DATACLASS}, {"A": new}) == ["breaking"]


BASE_PROTOCOL = protocol(run=method(param("query"), returns="str", is_async=True))


@pytest.mark.parametrize(
    "new_member",
    [
        method(param("query", annotation="bytes"), returns="str", is_async=True),  # assinatura
        method(param("query"), returns="str", is_async=False),  # async
        method(param("query"), returns="bytes", is_async=True),  # retorno
    ],
)
def test_protocol_member_changes_are_breaking(api_surface: ModuleType, new_member: dict[str, Any]) -> None:
    assert kinds(api_surface, {"P": BASE_PROTOCOL}, {"P": protocol(run=new_member)}) == ["breaking"]


def test_protocol_member_removed_is_breaking(api_surface: ModuleType) -> None:
    assert kinds(api_surface, {"P": BASE_PROTOCOL}, {"P": protocol()}) == ["breaking"]


def test_new_agent_pack_hook_with_default_in_pack_base_is_additive(api_surface: ModuleType) -> None:
    new = protocol(run=BASE_PROTOCOL["members"]["run"], routine=method(returns="None", in_base=True))
    assert kinds(api_surface, {"AgentPack": BASE_PROTOCOL}, {"AgentPack": new}) == ["additive"]


def test_new_protocol_member_without_default_is_breaking(api_surface: ModuleType) -> None:
    new = protocol(run=BASE_PROTOCOL["members"]["run"], routine=method(returns="None", in_base=False))
    assert kinds(api_surface, {"Retriever": BASE_PROTOCOL}, {"Retriever": new}) == ["breaking"]
    assert kinds(api_surface, {"AgentPack": BASE_PROTOCOL}, {"AgentPack": new}) == ["breaking"]


BASE_TYPEDDICT = typeddict(chunk_id=key(), page=key("int | None", required=False))


@pytest.mark.parametrize(
    "new_keys",
    [
        {"chunk_id": key()},  # chave removida
        {"chunk_id": key("int"), "page": key("int | None", required=False)},  # tipo alterado
        {"chunk_id": key(), "page": key("int | None", required=True)},  # passou a obrigatória
        {"chunk_id": key(readonly=False), "page": key("int | None", required=False)},  # perdeu ReadOnly
    ],
)
def test_typeddict_breaking_changes(api_surface: ModuleType, new_keys: dict[str, Any]) -> None:
    assert "breaking" in kinds(api_surface, {"C": BASE_TYPEDDICT}, {"C": typeddict(**new_keys)})


def test_new_optional_key_is_additive(api_surface: ModuleType) -> None:
    new = typeddict(chunk_id=key(), page=key("int | None", required=False), section=key(required=False))
    assert kinds(api_surface, {"C": BASE_TYPEDDICT}, {"C": new}) == ["additive"]


def test_new_required_key_is_breaking(api_surface: ModuleType) -> None:
    new = typeddict(chunk_id=key(), page=key("int | None", required=False), section=key(required=True))
    assert kinds(api_surface, {"C": BASE_TYPEDDICT}, {"C": new}) == ["breaking"]


BASE_FUNCTION = function(param("text"), param("strict", "KEYWORD_ONLY", "bool", "False"), returns="str")


@pytest.mark.parametrize(
    "new_function",
    [
        function(param("strict", "KEYWORD_ONLY", "bool", "False"), returns="str"),  # removido
        function(param("texto"), param("strict", "KEYWORD_ONLY", "bool", "False"), returns="str"),  # renomeado
        function(param("text", annotation="bytes"), param("strict", "KEYWORD_ONLY", "bool", "False"), returns="str"),
        function(param("text"), param("strict", "KEYWORD_ONLY", "bool", "True"), returns="str"),  # default
        function(param("text"), param("strict", "KEYWORD_ONLY", "bool", "False"), param("mode", "KEYWORD_ONLY")),
        function(param("text"), param("other"), param("strict", "KEYWORD_ONLY", "bool", "False"), returns="str"),
    ],
)
def test_function_breaking_changes(api_surface: ModuleType, new_function: dict[str, Any]) -> None:
    assert kinds(api_surface, {"f": BASE_FUNCTION}, {"f": new_function}) == ["breaking"]


def test_reordered_parameters_are_breaking(api_surface: ModuleType) -> None:
    old = function(param("a"), param("b"))
    assert kinds(api_surface, {"f": old}, {"f": function(param("b"), param("a"))}) == ["breaking"]


def test_new_optional_keyword_only_parameter_is_additive(api_surface: ModuleType) -> None:
    new = function(
        param("text"),
        param("strict", "KEYWORD_ONLY", "bool", "False"),
        param("limit", "KEYWORD_ONLY", "int", "10"),
        returns="str",
    )
    assert kinds(api_surface, {"f": BASE_FUNCTION}, {"f": new}) == ["additive"]


def test_return_type_change_is_breaking(api_surface: ModuleType) -> None:
    new = function(param("text"), param("strict", "KEYWORD_ONLY", "bool", "False"), returns="bytes")
    assert kinds(api_surface, {"f": BASE_FUNCTION}, {"f": new}) == ["breaking"]


def test_constant_value_change_is_breaking(api_surface: ModuleType) -> None:
    assert kinds(api_surface, {"K": constant("'a'")}, {"K": constant("'b'")}) == ["breaking"]


def test_issue_codes_are_compared_as_a_set(api_surface: ModuleType) -> None:
    old = {"ISSUE_CODES": constant(["a.x", "b.y"])}
    assert kinds(api_surface, old, {"ISSUE_CODES": constant(["a.x", "b.y", "c.z"])}) == ["additive"]
    assert kinds(api_surface, old, {"ISSUE_CODES": constant(["a.x"])}) == ["breaking"]


def test_deprecating_a_symbol_is_additive(api_surface: ModuleType) -> None:
    deprecated = copy.deepcopy(BASE_DATACLASS)
    deprecated["deprecated_since"] = "0.1.1"
    assert kinds(api_surface, {"A": BASE_DATACLASS}, {"A": deprecated}) == ["additive"]


def test_identical_snapshots_have_no_changes(api_surface: ModuleType) -> None:
    assert kinds(api_surface, {"A": BASE_DATACLASS}, {"A": copy.deepcopy(BASE_DATACLASS)}) == []


# ---------------------------------------------------------------- §8: bump exigido versus declarado


def verdict(api_surface: ModuleType, old: dict[str, Any], new: dict[str, Any], old_v: str, new_v: str) -> Any:
    return api_surface.evaluate(snapshot(old, version=old_v), snapshot(new, version=new_v))


def test_additive_change_requires_patch_in_0x(api_surface: ModuleType) -> None:
    assert verdict(api_surface, {}, {"A": BASE_DATACLASS}, "0.1.0", "0.1.0").failed
    result = verdict(api_surface, {}, {"A": BASE_DATACLASS}, "0.1.0", "0.1.1")
    assert (result.required, result.declared, result.failed) == ("patch", "patch", False)


def test_breaking_change_requires_minor_in_0x(api_surface: ModuleType) -> None:
    old = {"A": {**BASE_DATACLASS, "deprecated_since": "0.1.0"}}
    assert verdict(api_surface, old, {}, "0.1.4", "0.1.5").failed
    result = verdict(api_surface, old, {}, "0.1.4", "0.2.0")
    assert (result.required, result.failed) == ("minor", False)


def test_breaking_change_requires_major_from_1_0(api_surface: ModuleType) -> None:
    old = {"A": {**BASE_DATACLASS, "deprecated_since": "1.0.0"}}
    assert verdict(api_surface, old, {}, "1.2.0", "1.3.0").failed
    assert not verdict(api_surface, old, {}, "1.2.0", "2.0.0").failed


def test_head_already_in_new_series_accepts_more_breaking_changes(api_surface: ModuleType) -> None:
    old = {"A": {**BASE_DATACLASS, "deprecated_since": "0.1.0"}, "B": BASE_DATACLASS}
    new = {"B": dataclass_symbol(name=field())}
    assert not verdict(api_surface, old, new, "0.1.3", "0.2.0").failed


def test_removal_without_deprecation_fails_even_with_bump(api_surface: ModuleType) -> None:
    result = verdict(api_surface, {"A": BASE_DATACLASS}, {}, "0.1.4", "0.2.0")
    assert result.failed
    assert result.undeprecated_removals == ("axon_ai_contracts.A",)


# ---------------------------------------------------------------- contra o pacote real


def _dump_in_subprocess(seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    completed = subprocess.run(
        [sys.executable, str(TOOL_PATH), "dump"], env=env, capture_output=True, text=True, check=True
    )
    return completed.stdout


def test_dump_is_deterministic_across_processes() -> None:
    assert _dump_in_subprocess("1") == _dump_in_subprocess("2")


def test_typeddict_qualifiers_come_from_annotation_text(api_surface: ModuleType) -> None:
    modules = api_surface.dump()["modules"][MODULE]
    citation = modules["Citation"]["keys"]
    assert {name: info["required"] for name, info in citation.items()} == {
        "chunk_id": True,
        "document": False,
        "page": False,
        "section": False,
        "status": False,
        "version": False,
    }
    assert all(info["readonly"] for info in citation.values())
    message = modules["Message"]["keys"]
    assert {name: info["required"] for name, info in message.items()} == {
        "attachments": False,
        "content": True,
        "role": True,
    }
    assert all(info["readonly"] for info in message.values())


def test_not_required_key_in_synthetic_typeddict(api_surface: ModuleType, tmp_path: Path, monkeypatch) -> None:
    source = """
        from __future__ import annotations
        from typing_extensions import NotRequired, TypedDict

        class Sample(TypedDict):
            always: str
            sometimes: NotRequired[int]
    """
    (tmp_path / "sample_td.py").write_text(textwrap.dedent(source), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("sample_td")
    keys = api_surface.describe(module.Sample)["keys"]
    assert (keys["always"]["required"], keys["sometimes"]["required"]) == (True, False)
    assert keys["sometimes"]["annotation"] == "int"


def test_real_package_compared_with_itself(api_surface: ModuleType) -> None:
    current = api_surface.dump()
    assert api_surface.classify(current, json.loads(json.dumps(current))) == []
    assert "__version__" not in current["modules"][MODULE]
    assert current["modules"][MODULE]["AgentPack"]["members"]["tools"]["default_in_base"] is True
