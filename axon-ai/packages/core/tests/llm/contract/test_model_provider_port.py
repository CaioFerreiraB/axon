"""T010 — conformidade da porta `ModelProvider` (contracts/ports.md).

Roda contra todos os adapters da porta: o simulado (adapter em memória, princípio XIII) e os da camada compatível —
Ollama e, na Fase 3, OpenAI e OpenRouter — com transporte HTTP falso, que exercita tradução, parsing de streaming, uso
de tokens e mapeamento de erro sem tocar a rede (research R10, T031).
"""

from __future__ import annotations

from typing import Any

import pytest
from llm_testkit import MODEL, PORT_CASES, USAGE, OllamaCase

from axon_ai.llm.api import ModelCallFailed

MESSAGES: list[Any] = [{"role": "user", "content": "oi"}]
TOOLS: list[Any] = [{"name": "calculate", "description": "soma", "parameters": {"type": "object"}}]
FORMAT: dict[str, Any] = {"type": "json_object"}


@pytest.fixture(params=PORT_CASES, ids=[case.id for case in PORT_CASES])
def case(request: pytest.FixtureRequest) -> Any:
    return request.param()


async def test_resposta_unica_segue_o_contrato_001(case: Any) -> None:
    provider = case.ok()
    response = await provider.chat(MESSAGES, MODEL, stream=False)
    assert response["message"]["role"] == "assistant"
    assert response["message"]["content"] == "resposta"
    assert response["finish_reason"] == "stop"
    assert response["usage"] == USAGE


async def test_streaming_entrega_pedacos_incrementais(case: Any) -> None:
    provider = case.ok()
    chunks = [chunk async for chunk in await provider.chat(MESSAGES, MODEL, stream=True)]
    assert [chunk["delta"] for chunk in chunks[:2]] == ["Oi", " mundo"]
    assert "finish_reason" not in chunks[0]
    assert chunks[-1]["finish_reason"] == "stop"
    assert chunks[-1]["usage"] == USAGE


async def test_sem_usage_o_adapter_nao_inventa_numero(case: Any) -> None:
    provider = case.ok(usage=None)
    response = await provider.chat(MESSAGES, MODEL, stream=False)
    assert "usage" not in response
    chunks = [chunk async for chunk in await provider.chat(MESSAGES, MODEL, stream=True)]
    assert all("usage" not in chunk for chunk in chunks)


async def test_modelo_tools_e_formato_chegam_ao_provider(case: Any) -> None:
    provider = case.ok()
    await provider.chat(MESSAGES, MODEL, tools=TOOLS, response_format=FORMAT, stream=False)
    assert case.sent_model() == MODEL
    assert case.sent_tool_names() == ["calculate"]
    assert case.sent_response_format() == FORMAT


async def test_provider_inalcancavel_vira_erro_nomeado(case: Any) -> None:
    provider = case.failing("inalcançável")
    with pytest.raises(ModelCallFailed) as error:
        await provider.chat(MESSAGES, MODEL, stream=False)
    assert error.value.provider == case.name
    assert error.value.model == MODEL
    assert "inalcançável" in error.value.reason


async def test_erro_de_status_preserva_o_codigo(case: Any) -> None:
    provider = case.failing("429")
    with pytest.raises(ModelCallFailed) as error:
        await provider.chat(MESSAGES, MODEL, stream=False)
    assert "429" in error.value.reason


async def test_inatividade_no_stream_vira_erro_explicito(case: Any) -> None:
    provider = case.failing("sem resposta")
    with pytest.raises(ModelCallFailed) as error:
        async for _ in await provider.chat(MESSAGES, MODEL, stream=True):
            pass
    assert "sem resposta" in error.value.reason


async def test_probe_confirma_modelo_presente(case: Any) -> None:
    result = await case.ok().probe(MODEL)
    assert result.available
    assert result.detail is None


async def test_probe_nega_modelo_ausente_com_motivo(case: Any) -> None:
    result = await case.ok(models=("outro:1b",)).probe(MODEL)
    assert not result.available
    assert result.detail is not None
    assert MODEL in result.detail


async def test_probe_com_provider_fora_do_ar_nao_levanta(case: Any) -> None:
    result = await case.failing("inalcançável").probe(MODEL)
    assert not result.available
    assert result.detail


async def test_ready_diz_que_o_provider_esta_pronto(case: Any) -> None:
    """ADR-035: pronto sem modelo nenhum; o caso de fora do ar depende do provider (local ou remoto, abaixo)."""
    result = await case.ok().ready()
    assert result.available
    assert result.detail is None


async def test_ready_do_local_fora_do_ar_nao_levanta() -> None:
    case = OllamaCase()
    result = await case.failing("inalcançável").ready()
    assert not result.available
    assert result.detail is not None and "inalcançável" in result.detail


def test_adapters_cumprem_a_porta(case: Any) -> None:
    provider = case.ok()
    assert provider.name == case.name
    assert callable(provider.chat)
    assert callable(provider.probe)
    assert callable(provider.ready)
