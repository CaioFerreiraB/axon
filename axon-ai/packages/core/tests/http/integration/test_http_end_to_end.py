"""T011 — a conversa da Fase 1 acontecendo só por HTTP (SC-002).

Cinco módulos no mesmo caminho: API (008), motor (005), Pack Runtime (002) carregando o `axon-generic` (010) e Model
Router (006). Só o modelo é simulado.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from graph_testkit import RecordingTraceSink, provider
from http_testkit import CREATED, answer_of, app_with, chunks_of, has_done

from axon_ai.assistants.api import AssistantNotFound, Principal
from axon_ai.graph.adapters.clock import FixedClock as GraphFixedClock
from axon_ai.graph.adapters.langgraph import langgraph_runtime
from axon_ai.graph.domain.outcome import EMPTY_ANSWER
from axon_ai.graph.service import ExecutionService
from axon_ai.http.adapters.development import AnonymousAuthenticator
from axon_ai.llm.api import ModelPolicy, ModelRef
from axon_ai.llm.service import ModelRoutingService
from axon_ai.observability.api import ExecutionFinished, ExecutionStarted, ModelCall, ValidationRun
from axon_ai.packs.adapters.entry_points import EntryPointPackSource
from axon_ai.packs.adapters.memory import InMemoryPackConfigSource
from axon_ai.packs.ports import PackSettings
from axon_ai.packs.service import PackRuntime

MODEL = "qwen3:1.7b"
ASSISTANT = "geral"


class RealGrant:
    """O grant que a composition root montará na Fase 1, com a composição vinda do Pack Registry."""

    def __init__(self, composition: Any) -> None:
        self.assistant = ASSISTANT
        self.flow = "chat"
        self.composition = composition
        self.models = ModelPolicy(roles={"generation": ModelRef(provider="ollama", model=MODEL)}, allow=("ollama/*",))


class PackGrants:
    """Resolvedor que compõe os packs de verdade, como a 011 fará."""

    def __init__(self, packs: PackRuntime) -> None:
        self._packs = packs

    async def resolve(self, *, model: str, principal: Principal) -> RealGrant:
        if model.split("/", 1)[0] != ASSISTANT:
            raise AssistantNotFound(model)
        return RealGrant(self._packs.compose(["generic"]))


def _platform(llm: Any, trace: RecordingTraceSink) -> TestClient:
    packs = PackRuntime(EntryPointPackSource(), InMemoryPackConfigSource({"generic": PackSettings(enabled=True)}))
    packs.load()
    clock = GraphFixedClock(CREATED, readings=[1.0, 1.4])
    engine = ExecutionService(
        flows=langgraph_runtime(),
        hooks=packs,
        routing=ModelRoutingService(providers={"ollama": llm}, trace=trace, clock=clock),
        trace=trace,
        clock=clock,
    )
    return TestClient(app_with(engine, authenticator=AnonymousAuthenticator(), grants=PackGrants(packs)))


def _body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "model": f"{ASSISTANT}/{MODEL}",
        "messages": [{"role": "user", "content": "qual é a capital?"}],
    }
    return base | overrides


def test_conversa_em_streaming_atravessa_a_plataforma_inteira() -> None:
    trace = RecordingTraceSink()
    client = _platform(provider(deltas=("Bras", "ília")), trace)

    response = client.post("/v1/chat/completions", json=_body(stream=True))

    assert response.status_code == 200
    chunks = chunks_of(response.text)
    assert answer_of(chunks) == "Brasília"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert has_done(response.text)


def test_o_prompt_do_pack_de_referencia_chega_ao_modelo() -> None:
    trace = RecordingTraceSink()
    llm = provider()
    client = _platform(llm, trace)

    client.post("/v1/chat/completions", json=_body())

    enviadas = llm.calls[0]["messages"]
    assert enviadas[0]["role"] == "system"
    assert enviadas[0]["content"].strip()
    assert enviadas[-1]["content"] == "qual é a capital?"


def test_o_trace_da_requisicao_cobre_o_caminho_todo() -> None:
    trace = RecordingTraceSink()
    client = _platform(provider(), trace)

    response = client.post("/v1/chat/completions", json=_body())
    request_id = response.headers["x-request-id"]

    assert [event.request_id for event in trace.events] == [request_id] * len(trace.events)
    assert trace.of_type(ExecutionStarted)[0].packs == ("generic",)
    assert trace.of_type(ModelCall)[0].role == "generation"
    assert [(r.pack, r.validator) for r in trace.of_type(ValidationRun)] == [("generic", "non_empty_answer")]
    assert trace.of_type(ExecutionFinished)[0].ok is True


def test_resposta_vazia_e_reprovada_pelo_validator_do_pack_sem_virar_erro_http() -> None:
    """O validator do `axon-generic` reprova, mas reprovar é achado: a resposta sai com o apontamento, em 200."""
    trace = RecordingTraceSink()
    client = _platform(provider(deltas=("",)), trace)

    response = client.post("/v1/chat/completions", json=_body())

    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert {error["kind"] for error in payload["x_axon"]["errors"]} == {"ValidatorIssue", "EmptyAnswer"}
    assert payload["choices"][0]["message"]["content"] == EMPTY_ANSWER
    assert trace.of_type(ValidationRun)[0].ok is False


def test_assistant_desconhecido_responde_404() -> None:
    client = _platform(provider(), RecordingTraceSink())
    assert client.post("/v1/chat/completions", json=_body(model="outro")).status_code == 404
