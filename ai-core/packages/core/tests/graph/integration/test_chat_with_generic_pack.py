"""T015 — o caminho completo da US1: motor + Pack Runtime real + `ai-generic` real + provider simulado.

É o "Independent Test" que a própria US1 descreve, e o primeiro ponto do projeto em que quatro módulos se encontram
(002, 005, 006, 010). Só o modelo é simulado — é isso que mantém a suíte sem rede e determinística (research R13).
"""

from __future__ import annotations

from typing import Any

from graph_testkit import (
    MODEL,
    REFERENCE_TIME,
    RecordingTraceSink,
    provider,
    request,
)

from ai_core.graph.adapters.clock import FixedClock
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.api import FinalEvent, ProgressEvent, TokenEvent
from ai_core.graph.service import ExecutionService
from ai_core.llm.api import ModelPolicy, ModelRef
from ai_core.llm.service import ModelRoutingService
from ai_core.observability.api import ExecutionFinished, ExecutionStarted, ModelCall, ValidationRun
from ai_core.packs.adapters.entry_points import EntryPointPackSource
from ai_core.packs.adapters.memory import InMemoryPackConfigSource
from ai_core.packs.api import PackStatus
from ai_core.packs.ports import PackSettings
from ai_core.packs.service import PackRuntime


class RealGrant:
    """O grant que a 011 monta na Fase 1: composição vinda do Pack Registry e política de modelos da 006."""

    def __init__(self, composition: Any) -> None:
        self.assistant = "geral"
        self.flow = "chat"
        self.composition = composition
        self.models = ModelPolicy(
            roles={"generation": ModelRef(provider="ollama", model=MODEL)}, allow=("ollama/*",)
        )


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

    events = [event async for event in _engine(packs, trace, llm).run(RealGrant(composition), request())]

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
    async for _ in _engine(packs, trace, llm).run(RealGrant(packs.compose(["generic"])), request()):
        pass

    enviadas = llm.calls[0]["messages"]
    assert enviadas[0]["role"] == "system"
    assert enviadas[0]["content"] == packs.system_prompts(packs.compose(["generic"]))[0]
    assert enviadas[-1]["content"] == "qual é a capital?"


async def test_o_validator_do_pack_roda_e_aparece_no_trace() -> None:
    packs = _runtime()
    trace = RecordingTraceSink()
    async for _ in _engine(packs, trace, provider()).run(RealGrant(packs.compose(["generic"])), request()):
        pass

    runs = trace.of_type(ValidationRun)
    assert [(run.pack, run.validator, run.ok) for run in runs] == [("generic", "non_empty_answer", True)]


async def test_resposta_vazia_e_reprovada_pelo_validator_do_pack() -> None:
    """O `non_empty_answer` do `ai-generic` reprova, e a execução continua: é achado, não falha."""
    packs = _runtime()
    trace = RecordingTraceSink()
    llm = provider(deltas=("",))
    events = [
        event async for event in _engine(packs, trace, llm).run(RealGrant(packs.compose(["generic"])), request())
    ]

    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert trace.of_type(ValidationRun)[0].ok is False
    assert final.errors and final.errors[0].kind == "ValidatorIssue"
    assert trace.of_type(ExecutionFinished)[0].ok is True


async def test_o_trace_da_requisicao_tem_a_execucao_e_a_chamada_de_modelo() -> None:
    """A 006 emite a chamada de modelo; a 005 emite começo e fim. Nenhuma das duas duplica a outra."""
    packs = _runtime()
    trace = RecordingTraceSink()
    async for _ in _engine(packs, trace, provider()).run(RealGrant(packs.compose(["generic"])), request()):
        pass

    assert len(trace.of_type(ExecutionStarted)) == 1
    assert len(trace.of_type(ExecutionFinished)) == 1
    chamadas = trace.of_type(ModelCall)
    assert len(chamadas) == 1
    assert (chamadas[0].role, chamadas[0].provider, chamadas[0].model) == ("generation", "ollama", MODEL)
    assert {event.request_id for event in trace.events} == {"req-005-1"}
