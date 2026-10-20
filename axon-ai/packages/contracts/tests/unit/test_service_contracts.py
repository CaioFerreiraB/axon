"""Forma dos contratos de serviço: os falsos cumprem LLMProvider e MCPClient (FR-013, FR-014; T052)."""

from __future__ import annotations

from service_fakes import DEFAULT_CHUNKS, DEFAULT_RESPONSE, FakeLLMProvider, FakeMCPClient

from axon_ai_contracts import LLMProvider, MCPClient, ToolResult


def test_fakes_satisfy_the_protocols() -> None:
    assert isinstance(FakeLLMProvider(), LLMProvider)
    assert isinstance(FakeMCPClient(), MCPClient)
    assert not isinstance(object(), LLMProvider)


async def test_provider_without_and_with_stream() -> None:
    provider = FakeLLMProvider()
    response = await provider.chat([{"role": "user", "content": "ping"}], "modelo-teste")
    assert response == DEFAULT_RESPONSE
    stream = await provider.chat([{"role": "user", "content": "ping"}], "modelo-teste", stream=True)
    assert tuple([chunk async for chunk in stream]) == DEFAULT_CHUNKS
    assert [call["model"] for call in provider.calls] == ["modelo-teste", "modelo-teste"]


async def test_mcp_client_discovers_and_executes_by_alias() -> None:
    client = FakeMCPClient()
    [tool] = await client.discover_tools(["financas"])
    assert (tool.kind, tool.handler) == ("mcp", None)
    result = await client.execute("financas", "echo", {"x": 1})
    assert isinstance(result, ToolResult) and result.untrusted
    assert result.content == {"alias": "financas", "tool": "echo", "arguments": {"x": 1}}
