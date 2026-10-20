"""Suítes mínimas dos contratos de serviço (testing-kit.md, "Suítes dos contratos de serviço"; T053)."""

from __future__ import annotations

from service_fakes import FakeLLMProvider, FakeMCPClient

from axon_ai_contracts import ToolResult, ToolSpec
from axon_ai_contracts.testing import acheck_llm_provider, acheck_mcp_client


async def _llm_codes(provider: object) -> list[str]:
    return [issue.code for issue in await acheck_llm_provider(provider)]


async def _mcp_codes(client: object) -> list[str]:
    return [issue.code for issue in await acheck_mcp_client(client, alias="financas", tool="echo")]


async def test_fakes_pass_both_suites() -> None:
    assert await _llm_codes(FakeLLMProvider()) == []
    assert await _mcp_codes(FakeMCPClient()) == []


async def test_invalid_responses() -> None:
    no_finish = {"message": {"role": "assistant", "content": "x"}}
    wrong_role = {"message": {"role": "user", "content": "x"}, "finish_reason": "stop"}
    assert await _llm_codes(FakeLLMProvider(response=no_finish)) == ["llm.response.invalid"]
    assert await _llm_codes(FakeLLMProvider(response=wrong_role)) == ["llm.response.invalid"]


async def test_exception_is_reported_with_its_message() -> None:
    issues = await acheck_llm_provider(FakeLLMProvider(error=RuntimeError("fora do ar")))
    assert {issue.code for issue in issues} == {"llm.response.invalid", "llm.stream.invalid"}
    assert all("fora do ar" in issue.message for issue in issues)


async def test_invalid_streams() -> None:
    finish_in_middle = ({"delta": "a", "finish_reason": "stop"}, {"delta": "b", "finish_reason": "stop"})
    missing_finish = ({"delta": "a"}, {"delta": "b"})
    assert await _llm_codes(FakeLLMProvider(chunks=finish_in_middle)) == ["llm.stream.invalid"]
    assert await _llm_codes(FakeLLMProvider(chunks=missing_finish)) == ["llm.stream.invalid"]


async def test_invalid_mcp_discovery() -> None:
    async def handler(invocation: object) -> object:
        return None

    native = ToolSpec(name="echo", description="d", parameters={}, kind="native", handler=handler)
    assert await _mcp_codes(FakeMCPClient(tools=(native,))) == ["mcp.discovery.invalid"]


async def test_invalid_mcp_result() -> None:
    trusted = ToolResult(content="x", untrusted=False)
    assert await _mcp_codes(FakeMCPClient(result=trusted)) == ["mcp.result.invalid"]
