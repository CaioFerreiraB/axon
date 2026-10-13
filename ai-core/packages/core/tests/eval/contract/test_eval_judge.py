"""O juiz pelo Model Router (research R19; T033): saída estruturada, request_id por julgamento, falha vira ausência."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_core.eval.adapters.judge import RoutedJudge
from ai_core.eval.api import EvalInputError
from ai_core.eval.domain.judging import RESPONSE_FORMAT
from ai_core.graph.adapters.clock import FixedClock
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.api import ModelCallFailed
from ai_core.llm.service import ModelRoutingService
from ai_core.observability.api import ModelCall, TraceEvent

pytestmark = pytest.mark.us3


class Sink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def routing(provider: ScriptedProvider, sink: Sink) -> ModelRoutingService:
    return ModelRoutingService(
        providers={"juiz": provider}, trace=sink, clock=FixedClock(datetime(2026, 10, 7, tzinfo=UTC))
    )


async def test_julgamento_estruturado_com_request_id_proprio() -> None:
    sink = Sink()
    provider = ScriptedProvider(name="juiz", content='{"faithfulness": 0.75, "coverage": null}')
    juiz = RoutedJudge(routing(provider, sink), "juiz/modelo-x")
    assert juiz.name == "juiz/modelo-x"
    julgamento = await juiz.judge(
        question="Q?", answer="R.", passages=["trecho"], reference=None, request_id="eval-1-q001:judge:1"
    )
    assert (julgamento.faithfulness, julgamento.coverage) == (0.75, None)
    (chamada,) = provider.calls
    assert chamada["response_format"] == RESPONSE_FORMAT and chamada["model"] == "modelo-x"
    assert [e.request_id for e in sink.events if isinstance(e, ModelCall)] == ["eval-1-q001:judge:1"]


@pytest.mark.parametrize("model", ["sem-barra", "desconhecido/modelo"])
def test_juiz_invalido_falha_antes_da_rodada(model: str) -> None:
    with pytest.raises(EvalInputError):
        RoutedJudge(routing(ScriptedProvider(name="juiz"), Sink()), model)


@pytest.mark.parametrize(
    "provider",
    [
        ScriptedProvider(name="juiz", content="não é json"),
        ScriptedProvider(name="juiz", error=ModelCallFailed(provider="juiz", model="m", reason="fora do ar")),
    ],
)
async def test_falha_vira_julgamento_ausente(provider: ScriptedProvider) -> None:
    juiz = RoutedJudge(routing(provider, Sink()), "juiz/m")
    julgamento = await juiz.judge(question="Q", answer="R", passages=[], reference="ref", request_id="r")
    assert (julgamento.faithfulness, julgamento.coverage) == (None, None)
