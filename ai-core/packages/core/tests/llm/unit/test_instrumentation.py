"""T013 — o que o cliente devolvido pelo roteador registra no Trace Sink (FR-008, research R7)."""

from __future__ import annotations

from typing import Any

import pytest
from llm_testkit import MODEL, REQUEST_ID, ScriptedCase, policy

from ai_core.llm.adapters.clock import ScriptedClock
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.api import ModelCallFailed, RoleNotConfigured
from ai_core.llm.service import ModelRoutingService
from ai_core.observability.api import ModelCall

MESSAGES: list[Any] = [{"role": "user", "content": "oi"}]


def service(provider: ScriptedProvider, trace: Any, clock: Any) -> ModelRoutingService:
    return ModelRoutingService(providers={provider.name: provider}, trace=trace, clock=clock)


async def test_dado_de_chamada_carrega_papel_provider_modelo_e_requisicao(
    provider: ScriptedProvider, trace: Any, clock: ScriptedClock
) -> None:
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    await router.for_role("generation").complete(MESSAGES)
    event = trace.events[0]
    assert isinstance(event, ModelCall)
    assert (event.request_id, event.role, event.provider, event.model) == (
        REQUEST_ID,
        "generation",
        "ollama",
        MODEL,
    )


async def test_duracao_vem_do_relogio_injetado(provider: ScriptedProvider, trace: Any) -> None:
    """250 ms entre as duas leituras programadas — o trace não lê o relógio do sistema (ADR-013)."""
    router = service(provider, trace, ScriptedClock([1.0, 1.25])).for_execution(policy=policy(), request_id=REQUEST_ID)
    await router.for_role("generation").complete(MESSAGES)
    assert trace.events[0].duration_ms == pytest.approx(250.0)


async def test_tokens_vem_do_usage_do_provider(trace: Any, clock: ScriptedClock) -> None:
    provider = ScriptedProvider(name="ollama", usage={"prompt_tokens": 11, "completion_tokens": 4})
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    await router.for_role("generation").complete(MESSAGES)
    assert (trace.events[0].input_tokens, trace.events[0].output_tokens) == (11, 4)


@pytest.mark.parametrize("stream", [False, True], ids=["completa", "streaming"])
async def test_custo_informado_vai_no_dado_de_chamada(trace: Any, clock: ScriptedClock, stream: bool) -> None:
    """ADR-035: o custo que o provider informa no `usage` chega ao `ModelCall`; sem ele, fica ausente."""
    provider = ScriptedProvider(name="ollama", usage={"prompt_tokens": 11, "completion_tokens": 4}, cost=0.0042)
    model = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID).for_role("generation")
    if stream:
        async for _ in model.stream(MESSAGES):
            pass
    else:
        await model.complete(MESSAGES)
    assert trace.events[0].cost_usd == pytest.approx(0.0042)


async def test_sem_custo_informado_o_custo_fica_ausente(provider: ScriptedProvider, trace: Any, clock: Any) -> None:
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    await router.for_role("generation").complete(MESSAGES)
    assert trace.events[0].cost_usd is None


async def test_sem_usage_os_tokens_ficam_ausentes(trace: Any, clock: ScriptedClock) -> None:
    provider = ScriptedProvider(name="ollama", usage=None)
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    await router.for_role("generation").complete(MESSAGES)
    assert (trace.events[0].input_tokens, trace.events[0].output_tokens) == (None, None)


async def test_falha_emite_com_desfecho_de_erro(trace: Any, clock: ScriptedClock) -> None:
    provider = ScriptedProvider(
        name="ollama", error=ModelCallFailed(provider="ollama", model=MODEL, reason="provider inalcançável")
    )
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    with pytest.raises(ModelCallFailed):
        await router.for_role("generation").complete(MESSAGES)
    assert trace.events[0].finish_reason == "error"
    assert trace.events[0].duration_ms == pytest.approx(250.0)


async def test_streaming_emite_uma_vez_ao_terminar(provider: ScriptedProvider, trace: Any, clock: Any) -> None:
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    async for _ in router.for_role("generation").stream(MESSAGES):
        assert trace.events == []  # nada é emitido no meio do stream
    assert len(trace.events) == 1
    assert trace.events[0].finish_reason == "stop"


async def test_streaming_abandonado_no_meio_ainda_emite(provider: ScriptedProvider, trace: Any, clock: Any) -> None:
    """Quem consome pode desistir (cliente HTTP desconectado); a chamada continua rastreável (SC-002)."""
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    iterator = router.for_role("generation").stream(MESSAGES)
    await anext(iterator)
    await iterator.aclose()  # type: ignore[attr-defined]
    assert len(trace.events) == 1


async def test_falha_no_meio_do_stream_emite_uma_vez(trace: Any, clock: Any) -> None:
    provider = ScriptedProvider(
        name="ollama",
        deltas=("Oi", " mundo"),
        error=ModelCallFailed(provider="ollama", model=MODEL, reason="sem resposta por 120s"),
        fail_after=1,
    )
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    with pytest.raises(ModelCallFailed):
        async for _ in router.for_role("generation").stream(MESSAGES):
            pass
    assert len(trace.events) == 1
    assert trace.events[0].finish_reason == "error"


async def test_resolucao_que_falha_antes_da_rede_nao_emite(provider: ScriptedProvider, trace: Any, clock: Any) -> None:
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    with pytest.raises(RoleNotConfigured):
        router.for_role("rerank")
    assert trace.events == []


async def test_resolver_o_papel_nao_emite_nada_por_si(provider: ScriptedProvider, trace: Any, clock: Any) -> None:
    router = service(provider, trace, clock).for_execution(policy=policy(), request_id=REQUEST_ID)
    router.for_role("generation")
    assert trace.events == []


async def test_duas_chamadas_dois_eventos(trace: Any) -> None:
    case = ScriptedCase()
    provider = case.ok()
    router = service(provider, trace, ScriptedClock([1.0, 1.25, 3.0, 3.5])).for_execution(
        policy=policy(), request_id=REQUEST_ID
    )
    model = router.for_role("generation")
    await model.complete(MESSAGES)
    await model.complete(MESSAGES)
    assert [event.duration_ms for event in trace.events] == [pytest.approx(250.0), pytest.approx(500.0)]
