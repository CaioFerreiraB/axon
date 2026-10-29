"""A geração declara o gráfico em JSON; o motor o tira do texto e o entrega como os de tool (ADR-054; R56)."""

from __future__ import annotations

import json
from typing import Any

from graph_testkit import ANSWER, FakeCapabilities, Grant, ScriptedController, agentic, engine, provider, request

from axon_ai.graph.api import ChartEvent, FinalEvent, TokenEvent
from axon_ai.graph.domain.chart_blocks import CHART_BLOCK_INSTRUCTION, MAX_BLOCK_CHARTS, OPEN

ROSCA = {
    "kind": "donut",
    "title": "Gastos",
    "series": [{"name": "Gastos", "points": [{"x": "A", "y": 2}, {"x": "B", "y": 3}]}],
}


async def coletar(stream: Any) -> list[Any]:
    return [event async for event in stream]


def bloco(value: object) -> str:
    return f"{OPEN}\n{json.dumps(value)}\n```"


async def rodar(*deltas: str) -> tuple[list[Any], Any]:
    llm = provider(deltas=deltas)
    motor = engine(capabilities=FakeCapabilities(), controller=ScriptedController((ANSWER,)), llm=llm)
    return await coletar(motor.run(agentic(), request())), llm


async def test_o_grafico_da_geracao_sai_como_chart_event_e_o_texto_sem_o_bloco() -> None:
    texto = f"Veja.\n\n{bloco(ROSCA)}\n\nB é maior."
    events, llm = await rodar(*(texto[i : i + 5] for i in range(0, len(texto), 5)))

    tokens = "".join(e.text for e in events if isinstance(e, TokenEvent))
    assert OPEN not in tokens and "B é maior." in tokens
    [desenho] = [e for e in events if isinstance(e, ChartEvent)]
    assert desenho.tool == "generate" and desenho.chart.kind == "donut"
    final = events[-1]
    assert isinstance(final, FinalEvent) and final.charts == (desenho.chart,) and OPEN not in final.answer
    assert any(m["content"] == CHART_BLOCK_INSTRUCTION for m in llm.calls[-1]["messages"])


async def test_bloco_invalido_some_e_vira_registro() -> None:
    events, _ = await rodar(f"Tentei.\n{bloco(ROSCA | {'kind': 'radar'})}\nfim")
    final = events[-1]
    assert final.charts == () and OPEN not in final.answer
    assert any(issue.kind == "ChartBlockInvalid" and issue.severity == "notice" for issue in final.errors)


async def test_repeticao_e_teto_de_graficos() -> None:
    outros = [ROSCA | {"title": f"G{i}"} for i in range(MAX_BLOCK_CHARTS + 2)]
    events, _ = await rodar(bloco(ROSCA), bloco(ROSCA), *(bloco(item) for item in outros))
    assert len(events[-1].charts) == MAX_BLOCK_CHARTS


async def test_o_chat_nao_recebe_o_aviso() -> None:
    llm = provider()
    await coletar(engine(llm=llm).run(Grant(), request()))
    assert all(m["content"] != CHART_BLOCK_INSTRUCTION for m in llm.calls[-1]["messages"])
