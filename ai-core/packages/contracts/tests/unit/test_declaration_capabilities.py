"""check_declaration: regras de tools, retrievers e validators (T028)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from axon_ai_contracts import (
    Chunk,
    ContractIssue,
    JSONValue,
    NamedRetriever,
    PackManifest,
    ToolInvocation,
    ToolSpec,
    TurnView,
    ValidationResult,
    ValidatorContext,
    check_declaration,
)

OBJECT_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


async def _handler(invocation: ToolInvocation) -> object:
    return None


def _sync_handler(invocation: ToolInvocation) -> object:
    return None


class _Retriever:
    async def search(
        self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None
    ) -> Sequence[Chunk]:
        return ()


class _SyncRetriever:
    def search(self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None) -> Sequence[Chunk]:
        return ()


class _Validator:
    def __init__(self, name: str) -> None:
        self.name = name

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        return ValidationResult(ok=True)


class _SyncValidator(_Validator):
    def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:  # type: ignore[override]
        return ValidationResult(ok=True)


def tool(name: str = "echo", **overrides: Any) -> ToolSpec:
    params: dict[str, Any] = {
        "name": name,
        "description": "Eco.",
        "parameters": OBJECT_SCHEMA,
        "kind": "native",
        "handler": _handler,
    }
    params.update(overrides)
    return ToolSpec(**params)


def retriever(name: str = "docs", impl: object | None = None) -> NamedRetriever:
    return NamedRetriever(name=name, description="Busca.", collections=frozenset({"d"}), retriever=impl or _Retriever())  # type: ignore[arg-type]


def issues(**kwargs: Any) -> tuple[ContractIssue, ...]:
    return check_declaration(
        pack_name="meu_pack", contract_version="0.2", manifest=PackManifest(name="meu_pack", version="0.1.0"), **kwargs
    )


def codes(**kwargs: Any) -> list[str]:
    return [issue.code for issue in issues(**kwargs)]


def test_valid_capabilities() -> None:
    assert codes(tools=[tool()], retrievers=[retriever()], validators=[_Validator("ok_validator")]) == []


@pytest.mark.parametrize("kind", ["retrieval", "mcp"])
def test_pack_declares_only_native_tools(kind: str) -> None:
    assert codes(tools=[tool(kind=kind, handler=None)]) == ["tool.not_native"]


@pytest.mark.parametrize("name", ["Echo", "eco-tool", "1echo", "a" * 49])
def test_tool_name_pattern(name: str) -> None:
    assert codes(tools=[tool(name)]) == ["tool.name.invalid"]


def test_duplicate_tool_name() -> None:
    assert codes(tools=[tool(), tool()]) == ["tool.duplicate_name"]


@pytest.mark.parametrize(
    "schema",
    [{"type": "array"}, {"properties": {}}, {"type": "object", "properties": {}, "required": ["x"]}],
)
def test_tool_parameters_structure(schema: dict[str, object]) -> None:
    assert codes(tools=[tool(parameters=schema)]) == ["tool.parameters.invalid"]


def test_sync_handler() -> None:
    assert codes(tools=[tool(handler=_sync_handler)]) == ["tool.handler.not_async"]


def test_retriever_rules() -> None:
    assert codes(retrievers=[retriever("Docs")]) == ["retriever.name.invalid"]
    assert codes(retrievers=[retriever(), retriever()]) == ["retriever.duplicate_name"]
    assert codes(tools=[tool("docs")], retrievers=[retriever("docs")]) == ["retriever.name_collision"]
    [issue] = issues(retrievers=[retriever(impl=_SyncRetriever())])
    assert (issue.code, issue.subject) == ("hook.not_async", "retriever:docs")


def test_validator_rules() -> None:
    assert codes(validators=[_Validator("Bad-Name")]) == ["validator.name.invalid"]
    assert codes(validators=[_Validator("v"), _Validator("v")]) == ["validator.duplicate_name"]
    [issue] = issues(validators=[_SyncValidator("v")])
    assert (issue.code, issue.subject) == ("hook.not_async", "validator:v")
