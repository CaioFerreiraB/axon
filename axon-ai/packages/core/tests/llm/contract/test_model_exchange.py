"""T066 — toque da Fase 9 na 006 (ADR-034; 009 R35): o `TracedModel` emite o `ModelExchange` depois do `ModelCall`, em
`complete` e em `stream` (saída acumulada), sem cabeçalho nem credencial."""

from __future__ import annotations

from typing import Any

import pytest
from llm_testkit import REQUEST_ID, RecordingTraceSink, policy

from axon_ai.llm.adapters.clock import ScriptedClock
from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.llm.service import ModelRoutingService
from axon_ai.observability.api import ExchangeMessage, ModelExchange

pytestmark = pytest.mark.us7

MESSAGES: Any = [
    {"role": "system", "content": "Você é útil."},
    {"role": "user", "content": "Oi"},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "1", "name": "generic.calculate", "arguments": '{"x": 1}'}],
    },
    {"role": "tool", "content": "2", "tool_call_id": "1"},
]


def service(provider: ScriptedProvider, trace: RecordingTraceSink) -> ModelRoutingService:
    return ModelRoutingService(providers={"ollama": provider}, trace=trace, clock=ScriptedClock([0.0] * 8))


def _model(trace: RecordingTraceSink, *deltas: str) -> Any:
    provider = ScriptedProvider(name="ollama", deltas=deltas or ("Olá", ", mundo"))
    return service(provider, trace).for_execution(policy=policy(), request_id=REQUEST_ID).for_role("generation")


async def test_complete_emite_as_mensagens_e_a_saida() -> None:
    trace = RecordingTraceSink()
    await _model(trace).complete(MESSAGES)
    (exchange,) = trace.exchanges
    assert isinstance(exchange, ModelExchange) and exchange.request_id == REQUEST_ID
    assert (exchange.role, exchange.provider) == ("generation", "ollama")
    assert exchange.messages == (
        ExchangeMessage(role="system", content="Você é útil."),
        ExchangeMessage(role="user", content="Oi"),
        ExchangeMessage(role="assistant", content='[tool generic.calculate: {"x": 1}]'),
        ExchangeMessage(role="tool", content="2"),
    )
    assert exchange.output and len(trace.events) == 1


async def test_stream_acumula_a_saida_e_emite_ao_terminar() -> None:
    trace = RecordingTraceSink()
    chunks = [chunk async for chunk in _model(trace, "Bra", "sília.").stream(MESSAGES[:2])]
    assert chunks and len(trace.exchanges) == 1
    assert trace.exchanges[0].output == "Brasília."


async def test_falha_nao_emite_conteudo() -> None:
    trace = RecordingTraceSink()
    from axon_ai.llm.api import ModelCallFailed

    provider = ScriptedProvider(name="ollama", error=ModelCallFailed(provider="ollama", model="m", reason="caiu"))
    model = service(provider, trace).for_execution(policy=policy(), request_id=REQUEST_ID).for_role("generation")
    with pytest.raises(ModelCallFailed):
        await model.complete(MESSAGES[:2])
    assert trace.exchanges == [] and len(trace.events) == 1
