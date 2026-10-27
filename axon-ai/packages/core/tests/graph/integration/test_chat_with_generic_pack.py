"""T015 — o caminho completo da US1: motor + Pack Runtime real + `axon-generic` real + provider simulado.

É o "Independent Test" que a própria US1 descreve, e o primeiro ponto do projeto em que quatro módulos se encontram
(002, 005, 006, 010). Só o modelo é simulado — é isso que mantém a suíte sem rede e determinística (research R13).
"""

from __future__ import annotations

from typing import Any

from graph_testkit import (
    MODEL,
    REFERENCE_TIME,
    Grant,
    RecordingTraceSink,
    provider,
    request,
)

from axon_ai.graph.adapters.clock import FixedClock
from axon_ai.graph.adapters.langgraph import langgraph_runtime
from axon_ai.graph.api import FinalEvent, ProgressEvent, TokenEvent
from axon_ai.graph.domain.outcome import EMPTY_ANSWER
from axon_ai.graph.service import ExecutionService
from axon_ai.llm.service import ModelRoutingService
from axon_ai.observability.api import ExecutionFinished, ExecutionStarted, ModelCall, ValidationRun
from axon_ai.packs.adapters.entry_points import EntryPointPackSource
from axon_ai.packs.adapters.memory import InMemoryPackConfigSource
from axon_ai.packs.api import PackStatus
from axon_ai.packs.ports import PackSettings
from axon_ai.packs.service import PackRuntime


def _runtime() -> PackRuntime:
    runtime = PackRuntime(EntryPointPackSource(), InMemoryPackConfigSource({"generic": PackSettings(enabled=True)}))
    runtime.load()
    return runtime


def _engine(packs: PackRuntime, trace: RecordingTraceSink, llm: Any) -> ExecutionService:
    clock = FixedClock(REFERENCE_TIME, readings=[1.0, 1.4])
    return ExecutionService(
        flows=langgraph_runtime(),
        hooks=packs,
        routing=ModelRoutingService(providers={"ollama": llm}, trace=trace, clock=clock),
        trace=trace,
        clock=clock,
    )


async def test_conversa_ponta_a_ponta_com_o_pack_de_referencia() -> None:
    packs = _runtime()
    assert packs.entry("generic") is not None
    assert packs.entry("generic").status is PackStatus.ENABLED  # type: ignore[union-attr]

    trace = RecordingTraceSink()
    llm = provider(deltas=("Bras", "ília"))
    composition = packs.compose(["generic"])

    events = [event async for event in _engine(packs, trace, llm).run(Grant(composition=composition), request())]

    assert [event.stage for event in events if isinstance(event, ProgressEvent)] == [
        "prepare_context",
        "generate",
        "validate_answer",
    ]
    assert [event.text for event in events if isinstance(event, TokenEvent)] == ["Bras", "ília"]
    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.answer == "Brasília"
    assert final.errors == ()


async def test_o_prompt_do_pack_entra_como_mensagem_de_sistema() -> None:
    packs = _runtime()
    llm = provider()
    trace = RecordingTraceSink()
    async for _ in _engine(packs, trace, llm).run(Grant(composition=packs.compose(["generic"])), request()):
        pass

    enviadas = llm.calls[0]["messages"]
    assert enviadas[0]["role"] == "system"
    assert enviadas[0]["content"] == packs.system_prompts(packs.compose(["generic"]))[0]
    assert enviadas[-1]["content"] == "qual é a capital?"


async def test_o_validator_do_pack_roda_e_aparece_no_trace() -> None:
    packs = _runtime()
    trace = RecordingTraceSink()
    async for _ in _engine(packs, trace, provider()).run(Grant(composition=packs.compose(["generic"])), request()):
        pass

    runs = trace.of_type(ValidationRun)
    assert [(run.pack, run.validator, run.ok) for run in runs] == [("generic", "non_empty_answer", True)]


async def test_resposta_vazia_e_reprovada_pelo_validator_do_pack() -> None:
    """O `non_empty_answer` do `axon-generic` reprova, e a execução continua: é achado, não falha."""
    packs = _runtime()
    trace = RecordingTraceSink()
    llm = provider(deltas=("",))
    grant = Grant(composition=packs.compose(["generic"]))
    events = [event async for event in _engine(packs, trace, llm).run(grant, request())]

    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert trace.of_type(ValidationRun)[0].ok is False
    assert {issue.kind for issue in final.errors} == {"ValidatorIssue", "EmptyAnswer"}
    assert final.answer == EMPTY_ANSWER
    assert trace.of_type(ExecutionFinished)[0].ok is True


async def test_o_trace_da_requisicao_tem_a_execucao_e_a_chamada_de_modelo() -> None:
    """A 006 emite a chamada de modelo; a 005 emite começo e fim. Nenhuma das duas duplica a outra."""
    packs = _runtime()
    trace = RecordingTraceSink()
    async for _ in _engine(packs, trace, provider()).run(Grant(composition=packs.compose(["generic"])), request()):
        pass

    assert len(trace.of_type(ExecutionStarted)) == 1
    assert len(trace.of_type(ExecutionFinished)) == 1
    chamadas = trace.of_type(ModelCall)
    assert len(chamadas) == 1
    assert (chamadas[0].role, chamadas[0].provider, chamadas[0].model) == ("generation", "ollama", MODEL)
    assert {event.request_id for event in trace.events} == {"req-005-1"}
