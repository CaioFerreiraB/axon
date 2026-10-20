"""T009 — conformidade da rota (contracts/chat-completions.md), contra a app montada em processo."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from graph_testkit import RecordingTraceSink, ScriptedHooks, outcome, provider
from http_testkit import (
    CREATED,
    MODEL_ID,
    RejectingAuthenticator,
    StaticGrants,
    answer_of,
    app,
    body,
    chunks_of,
    has_done,
)

from axon_ai.llm.api import ModelCallFailed
from axon_ai.observability.api import ExecutionStarted

PREFIXES = ["/v1", "/private/v1"]


def post(client: TestClient, prefix: str = "/v1", **overrides: Any) -> Any:
    return client.post(f"{prefix}/chat/completions", json=body(**overrides))


# --- 1 e 2: os dois modos ------------------------------------------------------------------------------------


def test_streaming_devolve_chunks_no_formato_openai(client: TestClient) -> None:
    response = post(client, stream=True)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    chunks = chunks_of(response.text)
    assert chunks[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert answer_of(chunks) == "Brasília"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert has_done(response.text)


def test_resposta_completa_sem_streaming(client: TestClient) -> None:
    response = post(client)
    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["content"] == "Brasília"
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert payload["created"] == int(CREATED.timestamp())


# --- 3 e 4: identificador da requisição ----------------------------------------------------------------------


def test_identificador_da_requisicao_no_cabecalho_e_no_id(client: TestClient, trace: RecordingTraceSink) -> None:
    response = post(client)
    request_id = response.headers["x-request-id"]
    assert response.json()["id"] == f"chatcmpl-{request_id}"
    assert [event.request_id for event in trace.of_type(ExecutionStarted)] == [request_id]


def test_identificador_no_streaming_tambem(client: TestClient, trace: RecordingTraceSink) -> None:
    response = post(client, stream=True)
    request_id = response.headers["x-request-id"]
    assert chunks_of(response.text)[0]["id"] == f"chatcmpl-{request_id}"
    assert trace.of_type(ExecutionStarted)[0].request_id == request_id


# --- 5, 6 e 7: rejeições antes de qualquer execução -----------------------------------------------------------


@pytest.mark.parametrize("field", ["tools", "functions", "tool_choice", "function_call"])
def test_rejeita_campo_de_ampliacao_sem_tocar_o_provider(field: str) -> None:
    llm = provider()
    client = TestClient(app(llm=llm))
    response = client.post("/v1/chat/completions", json=body(**{field: [{"type": "function"}]}))
    assert response.status_code == 400
    assert response.json()["error"]["param"] == field
    assert response.json()["error"]["code"] == "widening_field"
    assert llm.calls == []


def test_rejeita_data_de_referencia_sem_tocar_o_provider() -> None:
    llm = provider()
    client = TestClient(app(llm=llm))
    response = client.post("/v1/chat/completions", json=body(reference_time="2026-01-01"))
    assert response.status_code == 400
    assert response.json()["error"]["param"] == "reference_time"
    assert response.json()["error"]["code"] == "reference_time"
    assert llm.calls == []


@pytest.mark.parametrize(
    "overrides",
    [{"messages": []}, {"messages": [{"role": "system", "content": "x"}]}, {"model": ""}],
)
def test_rejeita_corpo_invalido(client: TestClient, overrides: dict[str, Any]) -> None:
    assert post(client, **overrides).status_code == 400


# --- 8 e 9: identidade e visibilidade -------------------------------------------------------------------------


def test_assistant_desconhecido_responde_404_igual_ao_nao_autorizado() -> None:
    client = TestClient(app(grants=StaticGrants(known=("geral",))))
    inexistente = client.post("/v1/chat/completions", json=body(model="nao-existe/qwen3:1.7b"))
    assert inexistente.status_code == 404
    privado = client.post("/v1/chat/completions", json=body(model="privado/qwen3:1.7b"))
    assert privado.status_code == 404
    assert inexistente.json() == privado.json()


def test_assistant_desconhecido_em_streaming_tambem_responde_404() -> None:
    """O 404 sai como status, e não como stream: o primeiro chunk só é buscado depois de resolver o grant."""
    client = TestClient(app(grants=StaticGrants(known=("geral",))))
    response = client.post("/v1/chat/completions", json=body(model="nao-existe", stream=True))
    assert response.status_code == 404


def test_credencial_recusada_responde_401() -> None:
    client = TestClient(app(authenticator=RejectingAuthenticator()))
    assert client.post("/v1/chat/completions", json=body()).status_code == 401


# --- 10: as duas superfícies ----------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_rota_existe_identica_nas_duas_superficies(client: TestClient, prefix: str) -> None:
    response = post(client, prefix=prefix)
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Brasília"


def test_cada_superficie_se_identifica_para_o_autenticador() -> None:
    from http_testkit import SurfaceRecordingAuthenticator

    authenticator = SurfaceRecordingAuthenticator()
    client = TestClient(app(authenticator=authenticator))
    for prefix in PREFIXES:
        client.post(f"{prefix}/chat/completions", json=body())
    assert authenticator.surfaces == ["public", "private"]


# --- 11 e 12: falha de execução -------------------------------------------------------------------------------


def test_falha_depois_do_stream_aberto_encerra_o_stream_com_motivo() -> None:
    llm = provider(error=ModelCallFailed(provider="ollama", model="qwen3:1.7b", reason="inalcançável"))
    client = TestClient(app(llm=llm))
    response = client.post("/v1/chat/completions", json=body(stream=True))

    assert response.status_code == 200
    chunks = chunks_of(response.text)
    assert chunks[-1]["choices"][0]["finish_reason"] == "error"
    assert chunks[-1]["x_ai_core"]["errors"][0]["kind"] == "ModelCallFailed"
    assert has_done(response.text)


def test_falha_sem_streaming_responde_502_e_nao_200() -> None:
    """200 com marcador de erro seria degradação silenciosa; sem streaming ainda dá para escolher o status."""
    llm = provider(error=ModelCallFailed(provider="ollama", model="qwen3:1.7b", reason="inalcançável"))
    client = TestClient(app(llm=llm))
    response = client.post("/v1/chat/completions", json=body())

    assert response.status_code == 502
    payload = response.json()
    assert payload["choices"][0]["finish_reason"] == "error"
    assert payload["x_ai_core"]["errors"][0]["kind"] == "ModelCallFailed"
    assert response.headers["x-request-id"]
    # FR-022: o SDK oficial repete 5xx sozinho — e cada repetição rodaria a execução de novo.
    assert response.headers["x-should-retry"] == "false"


def test_execucao_so_com_avisos_e_sucesso_sem_streaming() -> None:
    """ADR-018: apontamento de validator (`notice`) não é falha — 200 e `stop`, com o motivo no campo extra."""
    hooks = ScriptedHooks(outcome=outcome(ok=False, issues=["sem fonte"]))
    response = TestClient(app(hooks=hooks)).post("/v1/chat/completions", json=body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert payload["x_ai_core"]["errors"][0]["kind"] == "ValidatorIssue"
    assert "x-should-retry" not in response.headers


def test_erro_anterior_a_execucao_nao_leva_o_cabecalho_de_nao_repetir() -> None:
    """Antes da execução nada rodou: repetir é seguro, e a resposta não diz o contrário."""
    response = TestClient(app(grants=StaticGrants(known=()))).post("/v1/chat/completions", json=body())
    assert response.status_code == 404
    assert "x-should-retry" not in response.headers


# --- progresso (research R5) ----------------------------------------------------------------------------------


def test_progresso_chega_no_stream_como_campo_extra_e_raciocinio_antes_do_texto(client: TestClient) -> None:
    """Fase 7 (FR-005, R34): antes do primeiro token, também como raciocínio; depois, só no campo extra."""
    chunks = chunks_of(post(client, stream=True).text)
    progresso = [c for c in chunks if "progress" in c.get("x_ai_core", {})]
    assert [c["x_ai_core"]["progress"]["stage"] for c in progresso] == [
        "prepare_context",
        "generate",
        "validate_answer",
    ]
    deltas = [c["choices"][0]["delta"] for c in progresso]
    assert deltas == [
        {"reasoning_content": "Preparando o contexto da pergunta…\n"},
        {"reasoning_content": "Escrevendo a resposta…\n"},
        {},
    ]
    primeiro_texto = next(i for i, c in enumerate(chunks) if c["choices"][0]["delta"].get("content"))
    assert all("reasoning_content" not in c["choices"][0]["delta"] for c in chunks[primeiro_texto:])


def test_o_modelo_pedido_volta_como_veio(client: TestClient) -> None:
    assert post(client).json()["model"] == MODEL_ID


# --- US6 cen. 1 (Fase 3, T053): progresso de tool no stream ----------------------------------------------------------


@pytest.mark.us6
def test_progresso_de_tool_chega_antes_dos_tokens() -> None:
    from graph_testkit import ANSWER, FakeCapabilities, ScriptedController, agentic, engine, tool_action
    from http_testkit import SurfaceRecordingAuthenticator, app_with

    class AgenticGrants:
        async def resolve(self, *, model: str, principal: Any) -> Any:
            return agentic()

    motor = engine(
        capabilities=FakeCapabilities(),
        controller=ScriptedController([tool_action("generic.calculate", expression="2+2"), ANSWER]),
    )
    client = TestClient(app_with(motor, authenticator=SurfaceRecordingAuthenticator(), grants=AgenticGrants()))
    response = client.post("/v1/chat/completions", json=body(stream=True))

    assert response.status_code == 200
    chunks = chunks_of(response.text)
    progresso = [c["x_ai_core"]["progress"] for c in chunks if "progress" in c.get("x_ai_core", {})]
    assert {"stage": "execute_tool", "detail": "generic.calculate"} in progresso
    primeiro_token = next(i for i, c in enumerate(chunks) if c["choices"][0]["delta"].get("content"))
    indice_tool = next(
        i for i, c in enumerate(chunks) if c.get("x_ai_core", {}).get("progress", {}).get("stage") == "execute_tool"
    )
    assert indice_tool < primeiro_token
    assert chunks[indice_tool]["choices"][0]["delta"] == {
        "reasoning_content": "Usando a ferramenta generic.calculate…\n"
    }, "Fase 7 (T066): a tool nomeada também como raciocínio"
    assert answer_of(chunks) == "Brasília"
