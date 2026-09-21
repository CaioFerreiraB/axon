"""T014 — o registro de nomes de flow (US5), que faz parte do seam e a 003 consome como dado."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from graph_testkit import Grant, engine, request

from ai_core.graph.api import ExecutionEvent, FinalEvent, UnknownFlow
from ai_core.graph.ports import ExecutionPlan


class SpyRuntime:
    """Runtime de teste: prova que acrescentar um flow é dado, não mudança de módulo (US5 cenário 1)."""

    def __init__(self, names: frozenset[str]) -> None:
        self._names = names
        self.executed: list[str] = []

    def names(self) -> frozenset[str]:
        return self._names

    async def events(self, plan: ExecutionPlan) -> AsyncIterator[ExecutionEvent]:
        self.executed.append(plan.flow)
        yield FinalEvent(answer=f"flow {plan.flow}")


def test_flows_lista_os_nomes_da_fase() -> None:
    assert engine().flows() == frozenset({"chat"})


async def test_grant_com_flow_inexistente_falha_nomeando_o_flow() -> None:
    with pytest.raises(UnknownFlow) as error:
        engine().run(Grant(flow="rag_first"), request())
    assert "rag_first" in str(error.value)


async def test_registrar_um_flow_novo_nao_exige_mudanca_em_outro_modulo(trace: Any) -> None:
    runtime = SpyRuntime(frozenset({"chat", "experimental"}))
    motor = engine(flows=runtime, trace=trace)
    assert motor.flows() == frozenset({"chat", "experimental"})

    events = [event async for event in motor.run(Grant(flow="experimental"), request())]
    assert runtime.executed == ["experimental"]
    assert events[-1].answer == "flow experimental"
