"""T038 — SC-002 e SC-005 sob controllers adversariais: o loop nunca passa do limite e nada acumulado se perde.

Hypothesis gera roteiros (tool válida, tool inexistente, JSON malformado, resposta, falha do controller) e limites
de 1 a 6. Sem teto de contexto declarado: a omissão por teto é o único caso em que um resultado não chega à geração,
e ela tem suíte própria (test_agentic_flow.py, item 19).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from graph_testkit import (
    ANSWER,
    FakeCapabilities,
    FakeSession,
    RecordingTraceSink,
    ScriptedController,
    ScriptedHooks,
    agentic,
    catalog_tool,
    controller_down,
    engine,
    provider,
    request,
    tool_action,
)
from hypothesis import given, settings
from hypothesis import strategies as st

from axon_ai.assistants.api import Limits
from axon_ai.graph.api import FinalEvent
from axon_ai.graph.domain.budget import is_tool_result
from axon_ai.observability.api import ControllerDecision

pytestmark = pytest.mark.us2

CALC = "generic.calculate"

LINES = st.sampled_from(["calc", "unknown", "garbage", "answer", "down"])


def materialize(kind: str, n: int) -> Any:
    return {
        "calc": lambda: tool_action(CALC, expression=f"{n}+{n}"),
        "unknown": lambda: tool_action("x.nao_existe", arg=n),
        "garbage": lambda: "{nada disso",
        "answer": lambda: ANSWER,
        "down": controller_down,
    }[kind]()


@settings(max_examples=60, deadline=None)
@given(st.lists(LINES, min_size=1, max_size=10), st.integers(min_value=1, max_value=6))
def test_limite_e_acumulo_sob_roteiros_adversariais(kinds: list[str], limit: int) -> None:
    script = [materialize(kind, n) for n, kind in enumerate(kinds)]
    controller = ScriptedController([*script, *([ANSWER] * 8)])
    session = FakeSession((catalog_tool(),))
    hooks = ScriptedHooks()
    trace = RecordingTraceSink()
    llm = provider(deltas=("ok",))
    motor = engine(capabilities=FakeCapabilities(session), controller=controller, hooks=hooks, trace=trace, llm=llm)

    async def execute() -> list[Any]:
        return [event async for event in motor.run(agentic(limits=Limits(max_iterations=limit)), request())]

    events = asyncio.run(execute())

    calls = len(controller.calls)
    assert calls <= limit
    assert len(session.calls) <= limit
    assert sum(isinstance(event, FinalEvent) for event in events) == 1
    assert isinstance(events[-1], FinalEvent)

    executed = [call.name for call in session.calls]
    sent = [m for m in llm.calls[0]["messages"] if is_tool_result(m)]
    assert len(sent) == len(executed)
    assert len(hooks.validate_views[-1].tool_results) == len(executed)

    consumed = [kinds[i] if i < len(kinds) else "answer" for i in range(calls)]
    answered = sum(kind != "down" for kind in consumed)
    by_limit = any(issue.kind == "IterationLimit" for issue in events[-1].errors)
    assert len(trace.of_type(ControllerDecision)) == answered + (1 if by_limit else 0)
