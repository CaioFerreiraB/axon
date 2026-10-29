"""Gráficos na execução (ADR-052, item 2; FR-024; research R53).

Os gráficos das tools vão ao usuário, depois do desfecho da tool, e não ao modelo, que vê só a marca no resultado
cercado (004).
"""

from __future__ import annotations

from typing import Any

from graph_testkit import (
    ANSWER,
    FakeCapabilities,
    FakeSession,
    ScriptedController,
    agentic,
    catalog_tool,
    engine,
    provider,
    request,
    tool_action,
)

from axon_ai.graph.api import AttachmentEvent, ChartEvent, FinalEvent, StepFinished
from axon_ai.graph.domain.images import CHARTS_INSTRUCTION
from axon_ai_contracts import Attachment, Chart, ChartPoint, ChartSeries


def rosca(title: str) -> Chart:
    pontos = (ChartPoint(x="Moradia", y=2100), ChartPoint(x="Mercado", y=1250))
    return Chart(kind="donut", title=title, series=(ChartSeries(name="Gastos", points=pontos),))


ROSCA = rosca("Gastos por categoria")
OUTRO = rosca("Gastos de setembro")
IMAGEM = Attachment(mime="image/png", data=b"\x89PNG\r\n\x1a\n" + b"g" * 50)


async def coletar(stream: Any) -> list[Any]:
    return [event async for event in stream]


async def test_grafico_da_tool_vai_ao_usuario_depois_do_desfecho_e_nao_ao_modelo() -> None:
    session = FakeSession(
        (catalog_tool("generic.chart"),),
        charts={"generic.chart": (ROSCA, OUTRO)},
        attachments={"generic.chart": (IMAGEM,)},
    )
    llm = provider(deltas=("Pronto.",))
    controller = ScriptedController((tool_action("generic.chart", expression="x"), ANSWER))
    motor = engine(capabilities=FakeCapabilities(session), controller=controller, llm=llm)

    events = await coletar(motor.run(agentic(), request()))

    executed = next(i for i, e in enumerate(events) if isinstance(e, StepFinished) and e.stage == "execute_tool")
    side = [(i, e) for i, e in enumerate(events) if isinstance(e, AttachmentEvent | ChartEvent)]
    assert [type(e) for _, e in side] == [AttachmentEvent, ChartEvent, ChartEvent], "imagens, depois gráficos"
    assert all(i == executed + n + 1 for n, (i, _) in enumerate(side)), "logo depois do desfecho da tool"
    charts = [e for _, e in side if isinstance(e, ChartEvent)]
    assert [e.chart for e in charts] == [ROSCA, OUTRO] and {e.tool for e in charts} == {"generic.chart"}
    final = events[-1]
    assert isinstance(final, FinalEvent) and final.charts == (ROSCA, OUTRO) and final.attachments == (IMAGEM,)
    sent = [m for call in [*llm.calls, *controller.calls] for m in call["messages"]]
    assert not any("Moradia" in str(message["content"]) for message in sent), "os dados não vão ao modelo"
    assert {"role": "system", "content": CHARTS_INSTRUCTION} in llm.calls[-1]["messages"]


async def test_o_mesmo_grafico_de_duas_chamadas_sai_uma_vez() -> None:
    session = FakeSession((catalog_tool("generic.chart"),), charts={"generic.chart": (ROSCA, ROSCA)})
    script = (tool_action("generic.chart", expression="a"), tool_action("generic.chart", expression="b"), ANSWER)
    motor = engine(capabilities=FakeCapabilities(session), controller=ScriptedController(script))

    events = await coletar(motor.run(agentic(), request()))

    assert [e.chart for e in events if isinstance(e, ChartEvent)] == [ROSCA]
    assert events[-1].charts == (ROSCA,)


async def test_sem_grafico_o_final_vem_vazio() -> None:
    llm = provider()
    controller = ScriptedController((tool_action("generic.calculate", expression="1+1"), ANSWER))
    motor = engine(capabilities=FakeCapabilities(), controller=controller, llm=llm)
    events = await coletar(motor.run(agentic(), request()))
    assert events[-1].charts == () and not any(isinstance(e, ChartEvent) for e in events)
    assert all(message["content"] != CHARTS_INSTRUCTION for message in llm.calls[-1]["messages"])
