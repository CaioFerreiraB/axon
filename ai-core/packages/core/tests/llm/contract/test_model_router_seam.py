"""T012 — conformidade do seam Model Router (contracts/model-router.md).

Os itens que tocam I/O rodam contra os dois adapters da porta; os que falham antes da rede rodam uma vez, porque
provam justamente que nenhum provider é acionado.
"""

from __future__ import annotations

from typing import Any

import pytest
from llm_testkit import MODEL, PROVIDER_CASES, REQUEST_ID, USAGE, ScriptedCase, policy

from ai_core.llm.adapters.clock import ScriptedClock
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.adapters.openai import OpenAIProvider
from ai_core.llm.adapters.secrets import InMemorySecretResolver
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
    router = routing(provider, trace).for_execution(policy=policy(generation="openai/gpt-4o"), request_id=REQUEST_ID)
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


# --- Fase 3, US2: papéis da mesma política em providers diferentes (T028, research R24) ------------------------------

ACTION_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {"name": "acao", "schema": {"type": "object"}},
}
"""Formato de ação do controller — a guarda da US4 exige esquema, então a prova da US2 já o envia."""


@pytest.mark.us2
async def test_papeis_em_providers_diferentes(trace: Any) -> None:
    remoto = ScriptedProvider(name="openrouter", content='{"action": "answer"}')
    local = ScriptedProvider(name="ollama")
    service = ModelRoutingService(
        providers={"openrouter": remoto, "ollama": local},
        trace=trace,
        clock=ScriptedClock([1.0, 1.25, 2.0, 2.5]),
    )
    politica = policy(controller="openrouter/qwen/qwen3-8b", allow=("ollama/*", "openrouter/*"))
    router = service.for_execution(policy=politica, request_id=REQUEST_ID)

    controller = router.for_role("controller")
    generation = router.for_role("generation")
    assert controller.ref == ModelRef(provider="openrouter", model="qwen/qwen3-8b")
    assert generation.ref == ModelRef(provider="ollama", model=MODEL)

    await controller.complete(MESSAGES, response_format=ACTION_FORMAT)
    async for _ in generation.stream(MESSAGES):
        pass

    assert [(event.role, event.provider) for event in trace.events] == [
        ("controller", "openrouter"),
        ("generation", "ollama"),
    ]
    assert len(remoto.calls) == 1
    assert len(local.calls) == 1


# --- Fase 3, FR-011: remoto sem credencial na saúde e na chamada (T033) ----------------------------------------------


@pytest.mark.us3
async def test_saude_de_remoto_sem_credencial(trace: Any) -> None:
    service = ModelRoutingService(
        providers={"openai": OpenAIProvider(secrets=InMemorySecretResolver())},
        trace=trace,
        clock=ScriptedClock([1.0, 1.25]),
    )
    politica = policy(generation="openai/gpt-4o-mini", allow=("openai/*",))

    resultados = await service.check(politica)
    assert len(resultados) == 1
    assert not resultados[0].available
    assert "sem credencial" in (resultados[0].detail or "")
    assert "AI_CORE_OPENAI_API_KEY" in (resultados[0].detail or "")

    router = service.for_execution(policy=politica, request_id=REQUEST_ID)
    with pytest.raises(ModelCallFailed, match="AI_CORE_OPENAI_API_KEY"):
        await router.for_role("generation").complete(MESSAGES)
    assert len(trace.events) == 1
    assert trace.events[0].finish_reason == "error"


# --- Fase 3, US4: nenhuma chamada do controller sai sem esquema (T044, casos 11 e 12, research R17) -------------------

SEM_ESQUEMA = pytest.mark.parametrize(
    "formato",
    [None, {"type": "json_object"}, {"type": "json_schema", "json_schema": {"name": "acao"}}],
    ids=["sem-formato", "json_object", "json_schema-sem-schema"],
)


@pytest.mark.us4
@SEM_ESQUEMA
@pytest.mark.parametrize("modo", ["complete", "stream"])
async def test_controller_sem_restricao_e_recusado(trace: Any, formato: Any, modo: str) -> None:
    provider = ScriptedProvider(name="ollama", content='{"action": "answer"}')
    router = routing(provider, trace).for_execution(policy=policy(controller=f"ollama/{MODEL}"), request_id=REQUEST_ID)
    controller = router.for_role("controller")

    with pytest.raises(ModelCallFailed) as erro:
        if modo == "complete":
            await controller.complete(MESSAGES, response_format=formato)
        else:
            async for _ in controller.stream(MESSAGES, response_format=formato):
                pass

    assert erro.value.provider == "ollama"
    assert erro.value.model == MODEL
    assert "controller" in erro.value.reason
    assert provider.calls == []
    assert len(trace.events) == 1
    assert trace.events[0].role == "controller"
    assert trace.events[0].finish_reason == "error"


@pytest.mark.us4
async def test_generation_sem_formato_continua_aceito(trace: Any) -> None:
    provider = ScriptedProvider(name="ollama")
    router = routing(provider, trace, ScriptedClock([1.0, 1.25, 2.0, 2.5])).for_execution(
        policy=policy(), request_id=REQUEST_ID
    )
    generation = router.for_role("generation")

    await generation.complete(MESSAGES)
    async for _ in generation.stream(MESSAGES):
        pass

    assert len(provider.calls) == 2
    assert [event.finish_reason for event in trace.events] == ["stop", "stop"]


# --- Fase 3, US5: allowlist de provider e modelo, o cenário literal (T051, research R24) -----------------------------


@pytest.mark.us5
def test_allowlist_us5_literal(trace: Any) -> None:
    local = ScriptedProvider(name="ollama")
    remoto = ScriptedProvider(name="openai")
    service = ModelRoutingService(
        providers={"ollama": local, "openai": remoto}, trace=trace, clock=ScriptedClock([1.0])
    )

    so_local = policy(generation="openai/gpt-4o-mini", allow=("ollama/*",))
    with pytest.raises(ModelNotAllowed) as erro:
        service.for_execution(policy=so_local, request_id=REQUEST_ID).for_role("generation")
    assert "openai/gpt-4o-mini" in str(erro.value)
    assert "ollama/*" in str(erro.value)

    misto = policy(generation=f"ollama/{MODEL}", controller="openai/gpt-4o-mini", allow=("ollama/*",))
    router = service.for_execution(policy=misto, request_id=REQUEST_ID)
    with pytest.raises(ModelNotAllowed):
        router.for_role("controller")
    assert router.for_role("generation").ref == ModelRef(provider="ollama", model=MODEL)

    assert local.calls == []
    assert remoto.calls == []
    assert trace.events == []


# --- providers prontos (ADR-035) --------------------------------------------------------------------------------------


async def test_providers_lista_por_nome_com_a_prontidao_de_cada_um(trace: Any) -> None:
    service = ModelRoutingService(
        providers={
            "openrouter": ScriptedProvider(name="openrouter"),
            "openai": OpenAIProvider(secrets=InMemorySecretResolver()),
            "ollama": ScriptedProvider(name="ollama", unready="provider inalcançável em http://ollama.test/v1"),
        },
        trace=trace,
        clock=ScriptedClock([1.0, 1.25]),
    )

    statuses = await service.providers()

    assert [(s.name, s.ready) for s in statuses] == [("ollama", False), ("openai", False), ("openrouter", True)]
    assert "inalcançável" in (statuses[0].detail or "")
    assert "AI_CORE_OPENAI_API_KEY" in (statuses[1].detail or "")
    assert statuses[2].detail is None
    assert trace.events == []


async def test_providers_sem_nenhum_registrado(trace: Any) -> None:
    service = ModelRoutingService(providers={}, trace=trace, clock=ScriptedClock([1.0]))
    assert await service.providers() == ()
