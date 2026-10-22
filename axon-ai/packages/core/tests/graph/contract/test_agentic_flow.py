"""T037 — conformidade do flow `agentic` (US2): itens 13 a 23 de contracts/execution-engine.md.

Controller simulado (`ScriptedController`) no roteador real da 006, gateway falso da 004 (`FakeCapabilities`), hooks
programáveis. Não importa o framework de grafo (SC-001).
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

import pytest
from graph_testkit import (
    ANSWER,
    REFERENCE_TIME,
    REQUEST_ID,
    FakeCapabilities,
    FakeSession,
    RecordingTraceSink,
    ScriptedController,
    ScriptedHooks,
    agentic,
    catalog_tool,
    controller_down,
    engine,
    fenced,
    models,
    provider,
    request,
    tool_action,
)

from axon_ai.assistants.api import Limits
from axon_ai.capabilities.api import FENCE_INSTRUCTION, CatalogConflict
from axon_ai.graph.api import ExecutionRequestInvalid, FinalEvent, ProgressEvent, TokenEvent
from axon_ai.graph.domain.actions import response_format
from axon_ai.graph.domain.budget import OMITTED, estimate_tokens
from axon_ai.graph.domain.transcript import controller_messages, date_instruction
from axon_ai.observability.api import ControllerDecision, ExecutionError, ExecutionFinished, ToolCall
from axon_ai_contracts import ToolResult

pytestmark = pytest.mark.us2

CALC = "generic.calculate"


async def collect(events: Any) -> list[Any]:
    return [event async for event in events]


def run(
    *,
    script: list[Any],
    session: FakeSession | None = None,
    capabilities: FakeCapabilities | None = None,
    grant: Any = None,
    hooks: ScriptedHooks | None = None,
    trace: RecordingTraceSink | None = None,
    llm: Any = None,
) -> tuple[Any, ScriptedController, FakeCapabilities]:
    controller = ScriptedController(script)
    caps = capabilities or FakeCapabilities(session or FakeSession((catalog_tool(),), results={CALC: "4"}))
    motor = engine(capabilities=caps, controller=controller, hooks=hooks, trace=trace, llm=llm)
    return motor.run(grant or agentic(), request()), controller, caps


def final_of(events: list[Any]) -> FinalEvent:
    assert isinstance(events[-1], FinalEvent)
    assert sum(isinstance(event, FinalEvent) for event in events) == 1
    return events[-1]


def kinds(final: FinalEvent) -> list[tuple[str, str]]:
    return [(issue.kind, issue.severity) for issue in final.errors]


def decisions(trace: RecordingTraceSink) -> list[tuple[int, str, str | None, str | None]]:
    return [(d.iteration, d.action, d.tool, d.reason) for d in trace.of_type(ControllerDecision)]


# --- 13: tool e depois resposta (US2 cen. 1) ------------------------------------------------------------------------


async def test_tool_executada_uma_vez_resultado_acumulado_e_resposta_gerada() -> None:
    llm = provider(deltas=("São ", "4."))
    events, controller, caps = run(script=[tool_action(CALC, expression="2+2"), ANSWER], llm=llm)
    final = final_of(await collect(events))

    assert [call.name for call in caps.session.calls] == [CALC]
    assert dict(caps.session.calls[0].arguments) == {"expression": "2+2"}
    assert final.answer == "São 4."
    assert not [issue for issue in final.errors if issue.severity == "error"]

    (generation,) = llm.calls
    assert {"role": "system", "content": FENCE_INSTRUCTION} in generation["messages"]
    assert generation["messages"][-1] == {"role": "tool", "content": fenced(CALC, "4"), "tool_call_id": "call-1"}
    assert controller.calls[0]["response_format"] == response_format(list(caps.session.tools.values()))


# --- 14: limite (US2 cen. 2) ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("limits", [Limits(max_iterations=3), Limits()])
async def test_limite_3_e_controller_que_nunca_responde(limits: Limits) -> None:
    trace = RecordingTraceSink()
    script = [tool_action(CALC, expression=str(n)) for n in range(3)]
    events, controller, caps = run(script=script, grant=agentic(limits=limits), trace=trace)
    final = final_of(await collect(events))

    assert len(controller.calls) == 3
    assert len(caps.session.calls) == 3
    assert ("IterationLimit", "notice") in kinds(final)
    assert decisions(trace)[-1] == (3, "limit", None, "iterations")


# --- 15: ação malformada (US2 cen. 3) ---------------------------------------------------------------------------------


async def test_acao_malformada_conta_e_nao_interrompe() -> None:
    trace = RecordingTraceSink()
    events, controller, caps = run(script=["isso não é json", ANSWER], trace=trace)
    final = final_of(await collect(events))

    assert len(controller.calls) == 2
    assert ("InvalidAction", "notice") in kinds(final)
    assert decisions(trace) == [(1, "invalid", None, "JSON malformado"), (2, "answer", None, None)]
    assert controller.calls[1]["messages"][-1]["role"] == "user"
    assert "inválida" in controller.calls[1]["messages"][-1]["content"]
    assert caps.session.calls == []


# --- 16: tool fora do catálogo (US2 cen. 4) ---------------------------------------------------------------------------


async def test_tool_fora_do_catalogo_volta_ao_controller_e_conta() -> None:
    trace = RecordingTraceSink()
    events, controller, caps = run(script=[tool_action("x.nao_existe"), ANSWER], trace=trace)
    await collect(events)

    assert [call.name for call in caps.session.calls] == ["x.nao_existe"]
    last = controller.calls[1]["messages"][-1]
    assert last["role"] == "tool" and "tool inexistente: x.nao_existe" in last["content"]
    assert decisions(trace) == [(1, "tool", "x.nao_existe", None), (2, "answer", None, None)]


# --- 17: falha do controller (FR-006a) e MCP indisponível -------------------------------------------------------------


async def test_falha_do_controller_segue_para_a_geracao_sem_nova_tentativa() -> None:
    trace = RecordingTraceSink()
    llm = provider(deltas=("ok",))
    events, controller, _ = run(script=[controller_down()], trace=trace, llm=llm)
    final = final_of(await collect(events))

    assert len(controller.calls) == 1
    assert len(llm.calls) == 1
    assert final.answer == "ok"
    (falha,) = [issue for issue in final.errors if issue.kind == "ModelCallFailed"]
    assert falha.severity == "error" and falha.stage == "controller" and "ctrl/controlador" in falha.message
    assert [e.stage for e in trace.of_type(ExecutionError)] == ["controller"]
    assert trace.of_type(ExecutionFinished)[0].ok is False


async def test_mcp_indisponivel_e_erro_e_a_execucao_segue() -> None:
    session = FakeSession((catalog_tool(),), unavailable={"crm": "timeout na descoberta"})
    events, _, _ = run(script=[ANSWER], session=session)
    final = final_of(await collect(events))
    (issue,) = [issue for issue in final.errors if issue.kind == "McpUnavailable"]
    assert issue.severity == "error" and issue.stage == "load_capabilities" and "crm" in issue.message
    assert final.answer


# --- 18: catálogo vazio -----------------------------------------------------------------------------------------------


async def test_catalogo_vazio_nao_chama_o_controller() -> None:
    trace = RecordingTraceSink()
    events, controller, _ = run(script=[], session=FakeSession(()), trace=trace)
    final = final_of(await collect(events))
    assert controller.calls == []
    assert final.answer
    assert decisions(trace) == []


# --- 19: teto de contexto (FR-011) ------------------------------------------------------------------------------------


async def test_teto_para_o_loop_antes_da_chamada_que_passaria_e_omite_o_resultado_antigo() -> None:
    trace = RecordingTraceSink()
    llm = provider(deltas=("ok",))
    session = FakeSession((catalog_tool(),), results={CALC: "9" * 3000})
    today = date_instruction(REFERENCE_TIME, UTC)
    first = controller_messages(list(session.tools.values()), request().messages, (), today=today)
    ceiling = estimate_tokens(first) + 40
    events, controller, _ = run(
        script=[tool_action(CALC, expression="9")],
        session=session,
        grant=agentic(limits=Limits(max_context_tokens=ceiling)),
        trace=trace,
        llm=llm,
    )
    final = final_of(await collect(events))

    assert len(controller.calls) == 1
    assert ("ContextLimit", "notice") in kinds(final)
    assert decisions(trace)[-1] == (1, "limit", None, "context")
    trimmed = [issue for issue in final.errors if issue.kind == "ContextTrimmed"]
    assert trimmed and trimmed[0].severity == "notice" and "1" in trimmed[0].message

    sent = llm.calls[0]["messages"]
    assert sent[-1] == {"role": "tool", "content": OMITTED, "tool_call_id": "call-1"}
    assert sent[-2]["role"] == "assistant" and sent[-2]["tool_calls"][0]["id"] == "call-1"
    assert trace.of_type(ExecutionFinished)[0].ok is True


async def test_sem_teto_nada_sai() -> None:
    llm = provider(deltas=("ok",))
    session = FakeSession((catalog_tool(),), results={CALC: "9" * 3000})
    events, _, _ = run(script=[tool_action(CALC, expression="9"), ANSWER], session=session, llm=llm)
    final = final_of(await collect(events))
    assert not [issue for issue in final.errors if issue.kind.startswith("Context")]
    assert llm.calls[0]["messages"][-1]["content"] == fenced(CALC, "9" * 3000)


# --- 20: Turn View de validate (FR-010) ------------------------------------------------------------------------------


async def test_validate_recebe_os_resultados_entregues_na_ordem() -> None:
    hooks = ScriptedHooks()
    session = FakeSession((catalog_tool(), catalog_tool("crm.buscar")), results={CALC: "4", "crm.buscar": "Ana"})
    events, _, _ = run(
        script=[tool_action(CALC, expression="2+2"), tool_action("crm.buscar", nome="Ana"), ANSWER],
        session=session,
        hooks=hooks,
    )
    await collect(events)
    assert tuple(hooks.prepare_views[0].tool_results) == ()
    assert tuple(hooks.validate_views[-1].tool_results) == (
        ToolResult(content=fenced(CALC, "4")),
        ToolResult(content=fenced("crm.buscar", "Ana")),
    )


# --- 21: trace (FR-016) ----------------------------------------------------------------------------------------------


async def test_uma_decisao_por_chamada_sem_argumentos_e_sem_toolcall_do_motor() -> None:
    trace = RecordingTraceSink()
    events, _, _ = run(script=[tool_action(CALC, expression="segredo-2+2"), ANSWER], trace=trace)
    await collect(events)
    assert decisions(trace) == [(1, "tool", CALC, None), (2, "answer", None, None)]
    assert "segredo" not in repr(trace.of_type(ControllerDecision))
    assert trace.of_type(ToolCall) == []
    assert trace.of_type(ExecutionFinished)[0].ok is True


# --- 22: validação, contexto da sessão, progresso e falhas da abertura ------------------------------------------------


async def test_agentic_sem_papel_controller_levanta_na_chamada() -> None:
    llm = provider()
    controller = ScriptedController([])
    motor = engine(capabilities=FakeCapabilities(), controller=controller, llm=llm)
    with pytest.raises(ExecutionRequestInvalid, match="controller"):
        motor.run(agentic(models=models(controller=False)), request())
    assert controller.calls == [] and llm.calls == []


async def test_a_sessao_abre_com_o_contexto_da_execucao_e_os_filtros_das_fatias() -> None:
    hooks = ScriptedHooks(slice_update={"retrieval_filters": {"ano": 2026}, "outro": True})
    events, _, caps = run(script=[ANSWER], hooks=hooks)
    await collect(events)
    ((grant, context),) = caps.opened
    assert grant.flow == "agentic"
    assert context.request_id == REQUEST_ID
    assert context.reference_time == REFERENCE_TIME
    assert {pack: dict(filters) for pack, filters in context.retrieval_filters.items()} == {"generic": {"ano": 2026}}


async def test_progresso_do_loop_na_ordem() -> None:
    events, _, _ = run(script=[tool_action(CALC, expression="2+2"), ANSWER])
    progress = [(e.stage, e.detail) for e in await collect(events) if isinstance(e, ProgressEvent)]
    assert progress == [
        ("prepare_context", None),
        ("load_capabilities", None),
        ("controller", "iteração 1"),
        ("execute_tool", CALC),
        ("controller", "iteração 2"),
        ("generate", None),
        ("validate_answer", None),
    ]


async def test_conflito_de_catalogo_encerra_sem_gerar() -> None:
    llm = provider()
    trace = RecordingTraceSink()
    events, controller, _ = run(
        script=[], capabilities=FakeCapabilities(error=CatalogConflict(CALC)), llm=llm, trace=trace
    )
    collected = await collect(events)
    final = final_of(collected)
    assert [(i.stage, i.kind, i.severity) for i in final.errors] == [("load_capabilities", "CatalogConflict", "error")]
    assert not any(isinstance(event, TokenEvent) for event in collected)
    assert llm.calls == [] and controller.calls == []
    assert trace.of_type(ExecutionFinished)[0].ok is False


# --- 23: cancelamento no meio do loop --------------------------------------------------------------------------------


async def test_fechar_o_iterador_no_meio_do_loop_nao_levanta() -> None:
    trace = RecordingTraceSink()
    events, controller, _ = run(script=[tool_action(CALC, expression="2+2"), ANSWER], trace=trace)
    async for event in events:
        if isinstance(event, ProgressEvent) and event.stage == "execute_tool":
            break
    await events.aclose()
    assert len(controller.calls) == 1
    (finished,) = trace.of_type(ExecutionFinished)
    assert finished.ok is False and finished.reason == "cancelled"


# --- R50: data de referência, ação repetida, marcação de tool --------------------------------------------------------


async def test_a_data_de_referencia_vai_ao_controller_e_a_geracao() -> None:
    llm = provider(deltas=("ok",))
    events, controller, _ = run(script=[ANSWER], llm=llm)
    await collect(events)
    today = date_instruction(REFERENCE_TIME, UTC)
    assert today in str(controller.calls[0]["messages"][0]["content"])
    assert {"role": "system", "content": today} in llm.calls[0]["messages"]


async def test_tool_repetida_com_os_mesmos_argumentos_vai_a_geracao() -> None:
    trace = RecordingTraceSink()
    script = [tool_action(CALC, expression="2+2"), tool_action(CALC, expression="2+2")]
    events, controller, caps = run(script=script, trace=trace)
    final = final_of(await collect(events))

    assert len(controller.calls) == 2
    assert [call.name for call in caps.session.calls] == [CALC]
    assert ("RepeatedAction", "notice") in kinds(final)
    assert ("IterationLimit", "notice") not in kinds(final)
    assert decisions(trace) == [(1, "tool", CALC, None), (2, "tool", CALC, None)]


async def test_chamada_de_tool_escrita_como_texto_nao_chega_ao_usuario() -> None:
    llm = provider(deltas=("Veja: <tool_", "call>mango.grafico<arg_key>tipo</arg_key></tool_call>", " pronto."))
    events, _, _ = run(script=[ANSWER], llm=llm)
    emitted = await collect(events)
    final = final_of(emitted)

    assert final.answer == "Veja:  pronto."
    assert "".join(event.text for event in emitted if isinstance(event, TokenEvent)) == "Veja:  pronto."
    assert ("ToolMarkupRemoved", "notice") in kinds(final)
