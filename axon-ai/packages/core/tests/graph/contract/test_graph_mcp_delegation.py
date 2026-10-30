"""ADR-055: credencial sai do motor pelo gateway; não entra em estado/modelos/trace."""

from dataclasses import replace

import pytest
from capabilities_testkit import build as gateway
from graph_testkit import (
    ANSWER,
    RecordingTraceSink,
    ScriptedController,
    agentic,
    engine,
    provider,
    request,
    tool_action,
)
from mcp_testkit import FINANCEIRO_URL, global_draft
from mcp_testkit import build as registry

from axon_ai.mcp.api import DelegatedAuthorization


@pytest.mark.asyncio
async def test_execution_context_to_real_mcp_gateway_without_leaking():
    mcp = registry()
    await mcp.service.create_global(global_draft(auth_type="delegated"))
    caps = gateway()
    caps.service._mcp = mcp.service
    controller = ScriptedController([tool_action("financeiro.saldo"), ANSWER])
    llm, trace = provider(), RecordingTraceSink()
    motor = engine(capabilities=caps.service, controller=controller, llm=llm, trace=trace)
    grant = replace(agentic(), mcp_aliases=frozenset({"financeiro"}))
    auth = DelegatedAuthorization(alias="financeiro", endpoint=FINANCEIRO_URL, authorization="Bearer identity-secret")
    events = [e async for e in motor.run(grant, replace(request(), mcp_delegation=auth))]
    assert mcp.transport.calls
    assert all(t.headers["Authorization"] == "Bearer identity-secret" for _, t in mcp.transport.calls)
    assert "identity-secret" not in repr(events) + repr(llm.calls) + repr(controller.calls) + repr(trace.events)
    assert not [e for e in events[-1].errors if e.severity == "error"]
