"""T014 — o registro de nomes de flow (US5), que faz parte do seam e a 003 consome como dado."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from graph_testkit import FakeCapabilities, Grant, agentic, engine, request

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


# --- Fase 3 (T039; research R16) ------------------------------------------------------------------------------------


@pytest.mark.us2
def test_sem_gateway_o_agentic_nao_e_oferecido() -> None:
    assert engine().flows() == frozenset({"chat"})
    with pytest.raises(UnknownFlow, match="agentic"):
        engine().run(agentic(), request())


@pytest.mark.us2
def test_com_gateway_o_agentic_e_oferecido() -> None:
    assert engine(capabilities=FakeCapabilities()).flows() == frozenset({"chat", "agentic"})



# --- ADR-019 (003, passada de encaixe da Fase 3; T053): papéis por flow como dado ------------------------------------


@pytest.mark.us2
def test_papeis_por_flow_sem_gateway() -> None:
    assert engine().flow_roles() == {"chat": ("generation",)}


@pytest.mark.us2
def test_papeis_por_flow_com_gateway() -> None:
    motor = engine(capabilities=FakeCapabilities())
    assert motor.flow_roles() == {"chat": ("generation",), "agentic": ("controller", "generation")}
    assert set(motor.flow_roles()) == set(motor.flows())


@pytest.mark.us2
def test_flow_sem_regra_de_papeis_nao_exige_nenhum(trace: Any) -> None:
    motor = engine(flows=SpyRuntime(frozenset({"chat", "experimental"})), trace=trace)
    assert motor.flow_roles() == {"chat": ("generation",), "experimental": ()}
