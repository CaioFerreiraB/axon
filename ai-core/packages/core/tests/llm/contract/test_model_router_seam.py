"""T012 — conformidade do seam Model Router (contracts/model-router.md).

Os itens que tocam I/O rodam contra os dois adapters da porta; os que falham antes da rede rodam uma vez, porque
provam justamente que nenhum provider é acionado.
"""

from __future__ import annotations

from typing import Any

import pytest
from llm_testkit import MODEL, PROVIDER_CASES, REQUEST_ID, USAGE, ScriptedCase, policy

from ai_core.llm.adapters.clock import ScriptedClock
from ai_core.llm.api import (
    ModelCallFailed,
    ModelNotAllowed,
    ModelRef,
    RoleNotConfigured,
    UnknownProvider,
)
from ai_core.llm.service import ModelRoutingService
from ai_core.observability.api import ModelCall

MESSAGES: list[Any] = [{"role": "user", "content": "oi"}]


@pytest.fixture(params=PROVIDER_CASES, ids=[case.id for case in PROVIDER_CASES])
def case(request: pytest.FixtureRequest) -> Any:
    return request.param()


def routing(provider: Any, trace: Any, clock: Any = None) -> ModelRoutingService:
    return ModelRoutingService(
        providers={provider.name: provider}, trace=trace, clock=clock or ScriptedClock([1.0, 1.25])
    )


# --- 1 a 4: resolução, e as três falhas que acontecem antes de qualquer I/O ------------------------------------


def test_resolucao_devolve_cliente_ligado_ao_modelo(trace: Any) -> None:
    case = ScriptedCase()
    provider = case.ok()
    router = routing(provider, trace).for_execution(policy=policy(), request_id=REQUEST_ID)
    model = router.for_role("generation")
    assert model.role == "generation"
    assert model.ref == ModelRef.parse(f"ollama/{MODEL}")


def test_papel_nao_configurado_falha_sem_tocar_o_provider(trace: Any) -> None:
    case = ScriptedCase()
    provider = case.ok()
    router = routing(provider, trace).for_execution(policy=policy(), request_id=REQUEST_ID)
    with pytest.raises(RoleNotConfigured):
        router.for_role("controller")
    assert case.call_count() == 0
    assert trace.events == []


def test_modelo_fora_da_allowlist_falha_sem_tocar_o_provider(trace: Any) -> None:
    case = ScriptedCase()
    provider = case.ok()
    restrita = policy(generation="ollama/proibido:1b", allow=("ollama/qwen3:*",))
    router = routing(provider, trace).for_execution(policy=restrita, request_id=REQUEST_ID)
    with pytest.raises(ModelNotAllowed):
        router.for_role("generation")
    assert case.call_count() == 0
    assert trace.events == []


def test_provider_desconhecido_falha_sem_tocar_a_rede(trace: Any) -> None:
    case = ScriptedCase()
    provider = case.ok()
    router = routing(provider, trace).for_execution(
        policy=policy(generation="openai/gpt-4o"), request_id=REQUEST_ID
    )
    with pytest.raises(UnknownProvider) as error:
        router.for_role("generation")
    assert "openai" in str(error.value)
    assert case.call_count() == 0


# --- 5 e 6: geração ------------------------------------------------------------------------------------------


async def test_streaming_entrega_o_primeiro_pedaco_antes_do_fim(case: Any, trace: Any) -> None:
    router = routing(case.ok(), trace).for_execution(policy=policy(), request_id=REQUEST_ID)
    pedacos = [chunk async for chunk in router.for_role("generation").stream(MESSAGES)]
    assert [chunk["delta"] for chunk in pedacos[:2]] == ["Oi", " mundo"]
    assert pedacos[-1]["finish_reason"] == "stop"


async def test_complete_devolve_resposta_do_contrato_001(case: Any, trace: Any) -> None:
    router = routing(case.ok(), trace).for_execution(policy=policy(), request_id=REQUEST_ID)
    resposta = await router.for_role("generation").complete(MESSAGES)
    assert resposta["message"]["content"] == "resposta"
    assert resposta["usage"] == USAGE


# --- 7: provider fora do ar ----------------------------------------------------------------------------------


async def test_provider_indisponivel_nomeia_provider_e_modelo(case: Any, trace: Any) -> None:
    router = routing(case.failing("inalcançável"), trace).for_execution(policy=policy(), request_id=REQUEST_ID)
    with pytest.raises(ModelCallFailed) as error:
        await router.for_role("generation").complete(MESSAGES)
    assert "ollama" in str(error.value)
    assert MODEL in str(error.value)


async def test_streaming_indisponivel_propaga_o_erro(case: Any, trace: Any) -> None:
    router = routing(case.failing("sem resposta"), trace).for_execution(policy=policy(), request_id=REQUEST_ID)
    with pytest.raises(ModelCallFailed):
        async for _ in router.for_role("generation").stream(MESSAGES):
            pass


# --- 8: trace por chamada ------------------------------------------------------------------------------------


async def test_cada_chamada_emite_um_dado_de_trace(case: Any, trace: Any) -> None:
    router = routing(case.ok(), trace).for_execution(policy=policy(), request_id=REQUEST_ID)
    model = router.for_role("generation")
    await model.complete(MESSAGES)
    async for _ in model.stream(MESSAGES):
        pass
    assert len(trace.events) == 2
    assert all(isinstance(event, ModelCall) for event in trace.events)
    assert {event.role for event in trace.events} == {"generation"}
    assert {event.provider for event in trace.events} == {"ollama"}
    assert {event.model for event in trace.events} == {MODEL}


async def test_chamada_que_falha_tambem_deixa_rastro(case: Any, trace: Any) -> None:
    router = routing(case.failing("inalcançável"), trace).for_execution(policy=policy(), request_id=REQUEST_ID)
    with pytest.raises(ModelCallFailed):
        await router.for_role("generation").complete(MESSAGES)
    assert len(trace.events) == 1
    assert trace.events[0].finish_reason == "error"


# --- 9: saúde ------------------------------------------------------------------------------------------------


async def test_saude_devolve_um_resultado_por_papel_configurado(case: Any, trace: Any) -> None:
    provider = case.ok()
    completa = policy(controller=f"ollama/{MODEL}")
    resultados = await routing(provider, trace).check(completa)
    assert [health.role for health in resultados] == ["controller", "generation"]
    assert all(health.available for health in resultados)


async def test_saude_nega_modelo_ausente_com_motivo(case: Any, trace: Any) -> None:
    resultados = await routing(case.ok(models=("outro:1b",)), trace).check(policy())
    assert not resultados[0].available
    assert resultados[0].detail


async def test_saude_com_provider_fora_do_ar_nao_levanta(case: Any, trace: Any) -> None:
    resultados = await routing(case.failing("inalcançável"), trace).check(policy())
    assert not resultados[0].available


async def test_saude_de_provider_desconhecido_e_relatada_nao_levantada(trace: Any) -> None:
    provider = ScriptedCase().ok()
    resultados = await routing(provider, trace).check(policy(generation="openai/gpt-4o"))
    assert not resultados[0].available
    assert "openai" in (resultados[0].detail or "")


# --- 10: SC-001, trocar o modelo é configuração ---------------------------------------------------------------


async def test_trocar_o_modelo_e_so_configuracao(case: Any, trace: Any) -> None:
    provider = case.ok()
    service = routing(provider, trace, ScriptedClock([1.0, 1.25, 2.0, 2.5]))
    for modelo in (MODEL, "outro:1b"):
        router = service.for_execution(policy=policy(generation=f"ollama/{modelo}"), request_id=REQUEST_ID)
        await router.for_role("generation").complete(MESSAGES)
        assert case.sent_model() == modelo
    assert [event.model for event in trace.events] == [MODEL, "outro:1b"]
