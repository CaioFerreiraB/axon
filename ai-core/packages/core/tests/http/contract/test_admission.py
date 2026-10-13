"""T064 — admissão e fila (FR-016, FR-017, SC-003, SC-006; contracts/admission.md, verificações 1 a 5; R35).

O motor é o `HoldingEngine`: segura cada execução até o teste liberar, e conta as simultâneas. Os status passam pela app
(`httpx` sobre ASGI, na mesma volta do laço); a ordem e o instante dos chunks, pelo serviço direto.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from typing import Any

import httpx
import pytest
from http_testkit import (
    ANONYMOUS,
    MODEL_ID,
    HoldingEngine,
    StaticGrants,
    SurfaceRecordingAuthenticator,
    app_with,
    body,
    chunks_of,
    has_done,
)

from ai_core.assistants.api import Principal, RateLimited
from ai_core.http.domain.admission import AdmissionLimits
from ai_core.http.domain.chat_request import ChatRequest

pytestmark = pytest.mark.us6

PRINCIPAL = Principal(subject=ANONYMOUS, scheme="oidc")
REQUEST = ChatRequest(model=MODEL_ID, messages=({"role": "user", "content": "oi"},), stream=True)


class GrantsComCota(StaticGrants):
    """`cota/...` estoura a cota do par (429); o resto como o `StaticGrants`."""

    async def resolve(self, *, model: str, principal: Principal) -> Any:
        if model.startswith("cota/"):
            raise RateLimited("cota esgotada", retry_after=30)
        return await super().resolve(model=model, principal=principal)


def montar(limits: AdmissionLimits) -> tuple[Any, HoldingEngine]:
    engine = HoldingEngine()
    app = app_with(
        engine,
        authenticator=SurfaceRecordingAuthenticator(),
        grants=GrantsComCota(known=("geral", "cota")),
        admission=limits,
    )
    return app, engine


def client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://plataforma")


async def esperar(condicao: Callable[[], bool], segundos: float = 2.0) -> None:
    async with asyncio.timeout(segundos):
        while not condicao():
            await asyncio.sleep(0.005)


async def abrir(stream: AsyncIterator[dict[str, Any]], n: int = 1) -> list[dict[str, Any]]:
    return [await asyncio.wait_for(anext(stream), 1.0) for _ in range(n)]


async def drenar(stream: AsyncIterator[dict[str, Any]]) -> list[dict[str, Any]]:
    return [chunk async for chunk in stream]


def reasoning(chunk: dict[str, Any]) -> str | None:
    return chunk["choices"][0]["delta"].get("reasoning_content")


async def test_nunca_mais_execucoes_que_o_limite_e_recusa_antes_do_modelo() -> None:
    """Verificação 1 — SC-006, US6 cen. 3: 10 pedidos, 2 vagas, fila de 3."""
    app, engine = montar(AdmissionLimits(max_executions=2, queue_size=3, max_wait=timedelta(seconds=5)))
    async with client(app) as http:
        tarefas = [asyncio.create_task(http.post("/v1/chat/completions", json=body())) for _ in range(10)]
        await esperar(lambda: engine.running == 2 and sum(t.done() for t in tarefas) == 5)
        recusadas = [t.result() for t in tarefas if t.done()]
        assert engine.calls == 2
        engine.gate.set()
        respostas = await asyncio.gather(*tarefas)

    assert [r.status_code for r in recusadas] == [503] * 5
    assert all(r.json()["error"]["code"] == "overloaded" and r.headers["Retry-After"] == "5" for r in recusadas)
    assert "x-should-retry" not in recusadas[0].headers
    assert sorted(r.status_code for r in respostas) == [200] * 5 + [503] * 5
    assert engine.peak == 2
    assert engine.calls == 5, "nenhuma execução para os recusados"


async def test_quem_espera_ve_a_fila_na_hora_e_segue_ao_ganhar_a_vaga() -> None:
    """Verificação 2 — US6 cen. 2, SC-003."""
    app, engine = montar(AdmissionLimits(max_executions=2, queue_size=3, max_wait=timedelta(seconds=5)))
    service = app.state.chat_service
    primeiro, segundo = service.stream(REQUEST, PRINCIPAL), service.stream(REQUEST, PRINCIPAL)
    await abrir(primeiro)
    await abrir(segundo)

    terceiro = service.stream(REQUEST, PRINCIPAL)
    abertura, fila = await abrir(terceiro, 2)
    assert abertura["choices"][0]["delta"] == {"role": "assistant"}
    assert reasoning(fila) == "Aguardando uma vaga (posição 1 na fila)…\n"
    assert fila["x_ai_core"]["progress"] == {"stage": "queue", "detail": "1"}
    assert engine.calls == 0, "o aviso de fila vem antes de qualquer execução"

    engine.gate.set()
    await drenar(primeiro)
    await drenar(segundo)
    resto = await drenar(terceiro)
    assert reasoning(resto[0]) == "Escrevendo a resposta…\n"
    assert resto[1]["choices"][0]["delta"] == {"content": "ok"}
    assert resto[-1]["choices"][0]["finish_reason"] == "stop"
    assert engine.calls == 3


async def test_espera_esgotada_sem_streaming_e_503_e_em_streaming_e_fim_com_erro() -> None:
    """Verificação 3 — FR-017."""
    app, engine = montar(AdmissionLimits(max_executions=1, queue_size=2, max_wait=timedelta(milliseconds=50)))
    service = app.state.chat_service
    ocupando = service.stream(REQUEST, PRINCIPAL)
    await abrir(ocupando)

    async with client(app) as http:
        sem_stream = await http.post("/v1/chat/completions", json=body())
        com_stream = await http.post("/v1/chat/completions", json=body(stream=True))

    assert sem_stream.status_code == 503
    assert sem_stream.json()["error"]["code"] == "overloaded"
    assert sem_stream.headers["Retry-After"] == "1"
    assert com_stream.status_code == 200
    chunks = chunks_of(com_stream.text)
    assert reasoning(chunks[1]) == "Aguardando uma vaga (posição 1 na fila)…\n"
    final = chunks[-1]
    assert final["choices"][0]["finish_reason"] == "error"
    assert [(e["stage"], e["kind"]) for e in final["x_ai_core"]["errors"]] == [("admission", "QueueTimeout")]
    assert has_done(com_stream.text)
    assert engine.calls == 0, "nenhuma chamada de modelo para quem esperou"

    engine.gate.set()
    await drenar(ocupando)


async def test_quem_desiste_na_fila_sai_dela() -> None:
    """Verificação 4 — cliente que fecha o stream na fila não ocupa lugar."""
    app, engine = montar(AdmissionLimits(max_executions=1, queue_size=1, max_wait=timedelta(seconds=5)))
    service = app.state.chat_service
    ocupando = service.stream(REQUEST, PRINCIPAL)
    await abrir(ocupando)
    desistente = service.stream(REQUEST, PRINCIPAL)
    await abrir(desistente, 2)
    await desistente.aclose()

    seguinte = service.stream(REQUEST, PRINCIPAL)
    _, fila = await abrir(seguinte, 2)
    assert reasoning(fila) == "Aguardando uma vaga (posição 1 na fila)…\n", "a fila de 1 voltou a ter lugar"

    engine.gate.set()
    await drenar(ocupando)
    resto = await drenar(seguinte)
    assert resto[-1]["choices"][0]["finish_reason"] == "stop"
    assert engine.calls == 2


async def test_recusas_da_003_vem_antes_da_admissao() -> None:
    """Verificação 5 — 404 e 429 com vagas e fila cheias: nenhum ocupa lugar."""
    app, engine = montar(AdmissionLimits(max_executions=1, queue_size=1, max_wait=timedelta(seconds=5)))
    service = app.state.chat_service
    ocupando = service.stream(REQUEST, PRINCIPAL)
    await abrir(ocupando)
    esperando = service.stream(REQUEST, PRINCIPAL)
    await abrir(esperando, 2)

    async with client(app) as http:
        inexistente = await http.post("/v1/chat/completions", json=body(model="ninguem/x"))
        cota = await http.post("/v1/chat/completions", json=body(model="cota/x"))
        cheio = await http.post("/v1/chat/completions", json=body())

    assert inexistente.status_code == 404
    assert cota.status_code == 429
    assert cheio.status_code == 503

    engine.gate.set()
    await drenar(ocupando)
    await drenar(esperando)
    assert engine.calls == 2


@pytest.mark.parametrize(
    ("rota", "pedido"),
    [
        ("/v1/chat/completions", body()),
        ("/private/v1/chat/completions", body()),
        ("/v1/chat", {"assistant": "geral", "messages": [{"role": "user", "content": "oi"}]}),
    ],
)
async def test_sobrecarga_nas_duas_superficies_e_na_requisicao_nativa(rota: str, pedido: dict[str, Any]) -> None:
    """T066: o 503 de sobrecarga sai pela tabela de erros em toda rota de chat."""
    app, engine = montar(AdmissionLimits(max_executions=1, queue_size=0, max_wait=timedelta(seconds=7)))
    ocupando = app.state.chat_service.stream(REQUEST, PRINCIPAL)
    await abrir(ocupando)

    async with client(app) as http:
        resposta = await http.post(rota, json=pedido)

    assert resposta.status_code == 503
    assert resposta.json()["error"] == {
        "message": resposta.json()["error"]["message"],
        "type": "server_error",
        "param": None,
        "code": "overloaded",
    }
    assert resposta.headers["Retry-After"] == "7"
    engine.gate.set()
    await drenar(ocupando)
