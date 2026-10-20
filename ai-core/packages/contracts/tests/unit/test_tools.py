from __future__ import annotations

from datetime import UTC, datetime

import pytest

from axon_ai_contracts.tools import ToolInvocation, ToolResult, ToolSpec

NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def _handler(invocation: ToolInvocation) -> object:
    return invocation.arguments


def test_native_tool_spec() -> None:
    spec = ToolSpec(name="echo", description="Eco.", parameters={"type": "object"}, kind="native", handler=_handler)
    assert spec.mutates is False
    with pytest.raises(TypeError):
        spec.parameters["type"] = "array"  # type: ignore[index]


@pytest.mark.parametrize("kind", ["retrieval", "mcp"])
def test_non_native_tool_spec_has_no_handler(kind: str) -> None:
    spec = ToolSpec(name="t", description="d", parameters={}, kind=kind)  # type: ignore[arg-type]
    assert spec.handler is None


def test_tool_spec_rejects_invalid_kind_and_empty_fields() -> None:
    with pytest.raises(ValueError):
        ToolSpec(name="t", description="d", parameters={}, kind="python")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ToolSpec(name=" ", description="d", parameters={}, kind="mcp")
    with pytest.raises(ValueError):
        ToolSpec(name="t", description="", parameters={}, kind="mcp")


def test_tool_invocation_freezes_arguments_and_requires_aware_time() -> None:
    arguments = {"text": ["a"]}
    invocation = ToolInvocation(arguments=arguments, request_id="req-1", reference_time=NOW)
    arguments["text"].append("b")
    assert invocation.arguments == {"text": ("a",)}
    with pytest.raises(ValueError):
        ToolInvocation(arguments={}, request_id="req-1", reference_time=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        ToolInvocation(arguments={}, request_id="", reference_time=NOW)


def test_tool_result_defaults_and_freezing() -> None:
    result = ToolResult(content={"rows": [1, 2]})
    assert (result.untrusted, result.truncated, result.error) == (True, False, None)
    assert result.content == {"rows": (1, 2)}
