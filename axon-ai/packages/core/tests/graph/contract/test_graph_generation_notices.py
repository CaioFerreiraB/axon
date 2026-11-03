"""Avisos da geração depois do loop (FR-006b; research R54).

Sem ferramentas na geração, um modelo que ainda queria agir escreve a chamada como texto; o filtro de marcação a corta
e a resposta fica vazia. A geração passa a saber que as ferramentas acabaram e, no corte pelo limite, o que fazer.
"""

from __future__ import annotations

from typing import Any

from graph_testkit import (
    ANSWER,
    FakeCapabilities,
    Grant,
    ScriptedController,
    agentic,
    engine,
    provider,
    request,
    tool_action,
)

from axon_ai.graph.api import FinalEvent
from axon_ai.graph.domain.limits import DEFAULT_MAX_ITERATIONS, ITERATION_LIMIT
from axon_ai.graph.domain.transcript import LIMIT_INSTRUCTION, NO_TOOLS_INSTRUCTION


async def coletar(stream: Any) -> list[Any]:
    return [event async for event in stream]


def sistema(llm: Any) -> list[str]:
    return [m["content"] for m in llm.calls[-1]["messages"] if m["role"] == "system"]


async def test_depois_do_loop_a_geracao_sabe_que_nao_ha_ferramentas() -> None:
    llm = provider()
    controller = ScriptedController((tool_action("generic.calculate", expression="1+1"), ANSWER))
    motor = engine(capabilities=FakeCapabilities(), controller=controller, llm=llm)

    await coletar(motor.run(agentic(), request()))

    assert NO_TOOLS_INSTRUCTION in sistema(llm)
    assert LIMIT_INSTRUCTION not in sistema(llm), "o loop terminou por decisão, não pelo limite"


async def test_no_corte_pelo_limite_a_geracao_diz_o_que_faltou() -> None:
    llm = provider()
    script = tuple(tool_action("generic.calculate", expression=f"{n}+1") for n in range(DEFAULT_MAX_ITERATIONS))
    motor = engine(capabilities=FakeCapabilities(), controller=ScriptedController(script), llm=llm)

    events = await coletar(motor.run(agentic(), request()))

    final = events[-1]
    assert isinstance(final, FinalEvent) and any(issue.kind == ITERATION_LIMIT for issue in final.errors)
    assert NO_TOOLS_INSTRUCTION in sistema(llm) and LIMIT_INSTRUCTION in sistema(llm)
    assert sistema(llm).index(NO_TOOLS_INSTRUCTION) < sistema(llm).index(LIMIT_INSTRUCTION)


async def test_o_chat_nao_recebe_os_avisos() -> None:
    llm = provider()
    await coletar(engine(llm=llm).run(Grant(), request()))
    assert NO_TOOLS_INSTRUCTION not in sistema(llm) and LIMIT_INSTRUCTION not in sistema(llm)
