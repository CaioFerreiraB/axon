"""Desfecho de cada etapa no seam (ADR-028; contracts/execution-engine.md, "Desfecho de etapa").

Cada `ProgressEvent` tem o seu `StepFinished` antes da etapa seguinte; o desfecho traz chamadas, fontes e decisões, e
nunca o texto de trecho, de resultado ou de erro de tool. Mesmos andaimes das suítes de flow; não importa o framework de
grafo (SC-001).
"""

from __future__ import annotations

from typing import Any

import pytest
from graph_testkit import (
    ANSWER,
    MODEL,
    QUESTION,
    FakeCapabilities,
    FakeSession,
    Grant,
    ScriptedController,
    ScriptedHooks,
    ScriptedReranker,
    agentic,
    catalog_tool,
    chunk,
    controller_down,
    docs_session,
    engine,
    rag,
    rag_run,
    request,
    tool_action,
)

from axon_ai.graph.api import (
    CatalogOutcome,
    ControllerOutcome,
    FinalEvent,
    GateOutcome,
    GenerationOutcome,
    ProgressEvent,
    RagSettings,
    RerankOutcome,
    SourceRef,
    StepFinished,
    TokenEvent,
    ToolCallsOutcome,
    ToolCallSummary,
)

CALC = "generic.calculate"
CONTROLLER = "ctrl/controlador"
GENERATION = f"ollama/{MODEL}"
CHUNKS = (
    chunk("por#1", 0.9, document="POR", section="Regra 1", page=3, text="SEGREDO-DO-TRECHO"),
    chunk("por#2", 0.8, document="POR", section="Regra 2", page=4),
    chunk("est#1", 0.7, document="Estatuto", section="Art. 1", page=1),
)


async def collect(events: Any) -> list[Any]:
    return [event async for event in events]


def run(*, script: list[Any], session: FakeSession) -> Any:
    motor = engine(capabilities=FakeCapabilities(session), controller=ScriptedController(script))
    return motor.run(agentic(), request())


def steps(events: list[Any]) -> list[tuple[str, Any]]:
    return [(event.stage, event.outcome) for event in events if isinstance(event, StepFinished)]


def outcome_of(events: list[Any], stage: str) -> Any:
    (outcome,) = [found for name, found in steps(events) if name == stage]
    return outcome


def assert_paired(events: list[Any]) -> None:
    """Toda etapa que começou termina antes da próxima começar; o `FinalEvent` vem depois de tudo."""
    open_stage: str | None = None
    for event in events:
        if isinstance(event, ProgressEvent):
            assert open_stage is None, f"{event.stage} começou antes de {open_stage} terminar"
            open_stage = event.stage
        elif isinstance(event, StepFinished) and open_stage is not None:
            assert event.stage == open_stage
            open_stage = None
    assert open_stage is None
    assert isinstance(events[-1], FinalEvent)


# --- chat --------------------------------------------------------------------------------------------------------


async def test_chat_cada_etapa_termina_com_o_desfecho_e_os_tokens_vem_antes_do_fim_da_geracao() -> None:
    events = await collect(engine().run(Grant(), request()))
    assert_paired(events)
    assert steps(events) == [
        ("prepare_context", None),
        ("generate", GenerationOutcome(model=GENERATION, input_tokens=7, output_tokens=2)),
        ("validate_answer", None),
    ]
    last_token = max(index for index, event in enumerate(events) if isinstance(event, TokenEvent))
    generated = next(i for i, e in enumerate(events) if isinstance(e, StepFinished) and e.stage == "generate")
    assert last_token < generated


async def test_sem_streaming_so_o_evento_final() -> None:
    events = await collect(engine().run(Grant(), request(stream=False)))
    assert [type(event) for event in events] == [FinalEvent]


# --- agentic -------------------------------------------------------------------------------------------------------


@pytest.mark.us2
async def test_agentic_publica_catalogo_decisao_com_argumentos_e_a_chamada() -> None:
    session = FakeSession((catalog_tool(),), unavailable={"crm": "timeout na descoberta em 10.0.0.5"})
    events = run(script=[tool_action(CALC, expression="2+2"), ANSWER], session=session)
    collected = await collect(events)
    assert_paired(collected)

    assert [stage for stage, _ in steps(collected)] == [
        "prepare_context",
        "load_capabilities",
        "controller",
        "execute_tool",
        "controller",
        "generate",
        "validate_answer",
    ]
    assert outcome_of(collected, "load_capabilities") == CatalogOutcome(tools=1, unavailable=("crm",))
    first, second = [found for stage, found in steps(collected) if stage == "controller"]
    assert first == ControllerOutcome(
        iteration=1, action="tool", model=CONTROLLER, tool=CALC, arguments={"expression": "2+2"}
    )
    assert second == ControllerOutcome(iteration=2, action="answer", model=CONTROLLER)
    assert outcome_of(collected, "execute_tool") == ToolCallsOutcome(
        calls=(ToolCallSummary(tool=CALC, kind="native", arguments={"expression": "2+2"}, status="ok"),)
    )
    assert "10.0.0.5" not in repr(steps(collected))


@pytest.mark.us2
async def test_agentic_acao_invalida_falha_do_controller_e_tool_com_erro_sem_o_texto_do_erro() -> None:
    session = FakeSession((catalog_tool(),), failures={CALC: ("error", "SEGREDO-DO-ERRO")})
    events = run(script=["não é json", tool_action(CALC, expression="1"), controller_down()], session=session)
    collected = await collect(events)
    assert_paired(collected)

    decisions = [(found.action, found.reason) for stage, found in steps(collected) if stage == "controller"]
    assert decisions == [("invalid", "JSON malformado"), ("tool", None), ("failed", "ModelCallFailed")]
    (call,) = outcome_of(collected, "execute_tool").calls
    assert call.status == "error"
    assert "SEGREDO-DO-ERRO" not in repr(steps(collected))


# --- rag_first -----------------------------------------------------------------------------------------------------


@pytest.mark.us3
async def test_rag_first_publica_busca_rerank_e_portao_com_as_fontes_sem_texto() -> None:
    hooks = ScriptedHooks(rerankers={"docs": ScriptedReranker(order=["est#1", "por#1"])})
    events, _, _, _ = rag_run(session=docs_session(CHUNKS), hooks=hooks, settings=RagSettings(passages=2))
    collected = await collect(events)
    assert_paired(collected)

    assert [stage for stage, _ in steps(collected)] == [
        "prepare_context",
        "retrieve",
        "rerank",
        "gate",
        "generate",
        "validate_answer",
    ]
    (call,) = outcome_of(collected, "retrieve").calls
    assert call.tool == "docs.search" and call.kind == "retrieval" and call.status == "ok"
    assert dict(call.arguments) == {"query": QUESTION, "top_k": 20}
    assert call.sources == (
        SourceRef(document="POR", section="Regra 1", page=3),
        SourceRef(document="POR", section="Regra 2", page=4),
        SourceRef(document="Estatuto", section="Art. 1", page=1),
    )
    assert outcome_of(collected, "rerank") == RerankOutcome(
        candidates=3,
        kept=(
            SourceRef(document="Estatuto", section="Art. 1", page=1),
            SourceRef(document="POR", section="Regra 1", page=3),
        ),
    )
    assert outcome_of(collected, "gate") == GateOutcome(
        covered=True, route="generate", best_score=0.9, threshold=None, delivered=2
    )
    assert "SEGREDO-DO-TRECHO" not in repr(steps(collected))


@pytest.mark.us3
async def test_rag_first_reranker_que_falha_aparece_como_degradado() -> None:
    hooks = ScriptedHooks(rerankers={"docs": ScriptedReranker(error=RuntimeError("quebrou"))})
    events, _, _, _ = rag_run(session=docs_session(CHUNKS), hooks=hooks)
    rerank = outcome_of(await collect(events), "rerank")
    assert rerank.degraded == ("docs",) and len(rerank.kept) == 3


@pytest.mark.us3
@pytest.mark.parametrize(
    ("controller", "route"),
    [(False, "fallback"), (True, "controller")],
)
async def test_rag_first_portao_sem_cobertura_nao_entrega_trechos(controller: bool, route: str) -> None:
    script = [ANSWER] if controller else []
    events, _, _, _ = rag_run(session=docs_session(()), grant=rag(controller=controller), script=script)
    collected = await collect(events)
    assert_paired(collected)
    assert outcome_of(collected, "gate") == GateOutcome(covered=False, route=route, delivered=0)


@pytest.mark.us3
async def test_rag_first_busca_que_falha_publica_a_chamada_e_encerra_sem_gerar() -> None:
    session = docs_session(CHUNKS, failures={"docs.search": ("timeout", "SEGREDO-DO-ERRO")})
    events, _, _, _ = rag_run(session=session)
    collected = await collect(events)
    assert_paired(collected)
    assert [stage for stage, _ in steps(collected)] == ["prepare_context", "retrieve"]
    (call,) = outcome_of(collected, "retrieve").calls
    assert call.status == "timeout" and call.sources == ()
    assert "SEGREDO-DO-ERRO" not in repr(steps(collected))
