"""T040 — o caminho completo da US2: motor + Pack Runtime real + `axon-generic` + gateway real da 004.

É o encontro entre 004 e 005 que a conformidade, com gateway falso, não prova: o catálogo vem do `PackRuntime`
(seam Pack Toolset da 002), a tool nativa `calculate` do pack roda de verdade e o resultado chega cercado à geração.
Só os modelos são simulados (research R29).
"""

from __future__ import annotations

from typing import Any

import pytest
from graph_testkit import (
    ANSWER,
    REFERENCE_TIME,
    RecordingTraceSink,
    ScriptedController,
    agentic,
    provider,
    request,
    tool_action,
)

from axon_ai.capabilities.adapters.memory import InMemoryAuditLog
from axon_ai.capabilities.api import FENCE_INSTRUCTION, GatewayLimits
from axon_ai.capabilities.service import CapabilityService
from axon_ai.graph.adapters.clock import FixedClock
from axon_ai.graph.adapters.langgraph import langgraph_runtime
from axon_ai.graph.api import FinalEvent
from axon_ai.graph.domain.budget import RESULT_HEADER
from axon_ai.graph.service import ExecutionService
from axon_ai.llm.service import ModelRoutingService
from axon_ai.mcp.adapters.memory import InMemoryDiscoveryCache, InMemorySecretResolver, InMemoryServerStore
from axon_ai.mcp.ports import McpConfig
from axon_ai.mcp.service import McpService
from axon_ai.observability.api import (
    ControllerDecision,
    ExecutionFinished,
    ExecutionStarted,
    ModelCall,
    ToolCall,
    ValidationRun,
)
from axon_ai.packs.adapters.entry_points import EntryPointPackSource
from axon_ai.packs.adapters.memory import InMemoryPackConfigSource
from axon_ai.packs.ports import PackSettings
from axon_ai.packs.service import PackRuntime

pytestmark = pytest.mark.us2


def _platform(controller: ScriptedController, llm: Any, trace: RecordingTraceSink) -> tuple[ExecutionService, Any]:
    packs = PackRuntime(EntryPointPackSource(), InMemoryPackConfigSource({"generic": PackSettings(enabled=True)}))
    packs.load()
    clock = FixedClock(REFERENCE_TIME, readings=[1.0, 1.2])
    mcp = McpService(
        store=InMemoryServerStore(),
        config=McpConfig(),
        transports={},
        secrets=InMemorySecretResolver(),
        cache=InMemoryDiscoveryCache(clock),
        clock=clock,
    )
    capabilities = CapabilityService(
        pack_tools=packs, mcp=mcp, audit=InMemoryAuditLog(), trace=trace, clock=clock, limits=GatewayLimits()
    )
    engine = ExecutionService(
        flows=langgraph_runtime(),
        hooks=packs,
        routing=ModelRoutingService(providers={"ollama": llm, "ctrl": controller}, trace=trace, clock=clock),
        trace=trace,
        clock=clock,
        capabilities=capabilities,
    )
    return engine, packs


async def test_controller_pede_calculate_e_a_geracao_recebe_o_resultado_cercado() -> None:
    trace = RecordingTraceSink()
    controller = ScriptedController([tool_action("generic.calculate", expression="2+2"), ANSWER])
    llm = provider(deltas=("Dá ", "4."))
    engine, packs = _platform(controller, llm, trace)

    events = [event async for event in engine.run(agentic(composition=packs.compose(["generic"])), request())]

    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.answer == "Dá 4."
    assert not [issue for issue in final.errors if issue.severity == "error"]

    first = controller.calls[0]
    names = [
        branch["properties"].get("name", {}).get("const")
        for branch in first["response_format"]["json_schema"]["schema"]["anyOf"]
    ]
    assert names == [None, "generic.calculate", "generic.chart"]

    sent = llm.calls[0]["messages"]
    assert {"role": "system", "content": FENCE_INSTRUCTION} in sent
    resultado = sent[-1]
    assert resultado["role"] == "user" and resultado["content"].startswith(RESULT_HEADER)
    assert '<tool_result name="generic.calculate" status="ok"' in resultado["content"]
    assert '"result": 4' in resultado["content"]

    tipos = [
        (type(event).__name__, getattr(event, "role", None) or getattr(event, "action", None))
        for event in trace.events
        if isinstance(
            event, ExecutionStarted | ModelCall | ControllerDecision | ToolCall | ValidationRun | ExecutionFinished
        )
    ]
    assert tipos == [
        ("ExecutionStarted", None),
        ("ModelCall", "controller"),
        ("ControllerDecision", "tool"),
        ("ToolCall", None),
        ("ModelCall", "controller"),
        ("ControllerDecision", "answer"),
        ("ModelCall", "generation"),
        ("ValidationRun", None),
        ("ExecutionFinished", None),
    ]
    assert trace.of_type(ExecutionFinished)[0].ok is True
