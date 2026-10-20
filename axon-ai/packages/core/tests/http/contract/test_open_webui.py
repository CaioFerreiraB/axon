"""T069 — o pedido do Open WebUI v0.12 (US8 cen. 1 e 2; contracts/open-webui.md, verificações 1 e 2; research R38)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from graph_testkit import provider
from http_testkit import ANA_TOKEN, BIA_TOKEN, Platform, bearer, chunks_of, has_done
from open_webui_v0_12 import body, headers

pytestmark = pytest.mark.us8


def test_pedido_do_open_webui_recebe_streaming_com_a_timeline_de_status() -> None:
    """FR-005a, US6 cen. 5: a conexão manda `x-axon-progress: status`; o progresso vira status do Open WebUI
    (`event`), do começo ao fim, e nenhum raciocínio sai."""
    client = TestClient(Platform(llm=provider()).app)

    response = client.post("/v1/chat/completions", headers=headers(ANA_TOKEN), json=body())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "x-conversation-id" not in response.headers
    chunks = chunks_of(response.text)
    deltas = [c["choices"][0]["delta"] for c in chunks]
    assert not any(d.get("reasoning_content") for d in deltas)
    assert "".join(d.get("content", "") for d in deltas) == "Brasília"

    statuses = [(i, c["event"]["data"]) for i, c in enumerate(chunks) if "event" in c]
    assert all(c["event"]["type"] == "status" for c in chunks if "event" in c)
    assert all(deltas[i] == {} for i, _ in statuses), "status nunca leva texto no delta"
    primeiro_texto = next(i for i, d in enumerate(deltas) if d.get("content"))
    assert statuses[0][0] < primeiro_texto, "progresso visível antes da resposta"
    assert any(i > primeiro_texto for i, _ in statuses), "a timeline segue depois do primeiro texto"
    descriptions = [data["description"] for _, data in statuses]
    assert descriptions[0] == "Preparando o contexto da pergunta…"
    assert any(text.startswith("Resposta de ollama/") for text in descriptions)
    assert descriptions[-1].startswith("Concluído em ") and statuses[-1][1]["done"] is True
    assert [data["done"] for _, data in statuses].count(False) == 3, "um início por etapa do chat"

    assert all("conversation_id" not in c.get("x_axon", {}) for c in chunks)
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert has_done(response.text)


def test_sem_o_cabecalho_de_progresso_o_open_webui_recebe_raciocinio() -> None:
    """FR-005 (US6 cen. 4) continua valendo para a conexão que não manda o cabeçalho."""
    client = TestClient(Platform(llm=provider()).app)
    sem = {name: value for name, value in headers(ANA_TOKEN).items() if name != "x-axon-progress"}

    response = client.post("/v1/chat/completions", headers=sem, json=body())

    chunks = chunks_of(response.text)
    deltas = [c["choices"][0]["delta"] for c in chunks]
    primeiro_texto = next(i for i, d in enumerate(deltas) if d.get("content"))
    assert any(d.get("reasoning_content") for d in deltas[:primeiro_texto])
    assert not any(d.get("reasoning_content") for d in deltas[primeiro_texto:])
    assert all(d.get("reasoning_content", "\n").endswith("\n") for d in deltas)
    assert not any("event" in c for c in chunks)


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/chat"])
def test_modo_de_progresso_desconhecido_e_400_nas_duas_entradas(path: str) -> None:
    client = TestClient(Platform(llm=provider()).app)
    payload = body() if path.endswith("completions") else {"assistant": "geral", "messages": body()["messages"]}
    errado = headers(ANA_TOKEN) | {"x-axon-progress": "timeline"}

    response = client.post(path, headers=errado, json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_header"
    assert response.json()["error"]["param"] == "x-axon-progress"


def test_requisicao_nativa_tambem_mostra_a_timeline() -> None:
    client = TestClient(Platform(llm=provider()).app)
    payload = {"assistant": "geral", "messages": body()["messages"], "stream": True}

    response = client.post("/v1/chat", headers=headers(ANA_TOKEN), json=payload)

    assert response.status_code == 200
    assert any("event" in c for c in chunks_of(response.text))


def test_cada_token_ve_so_os_proprios_assistants() -> None:
    """US8 cen. 1 e 2: o Open WebUI guarda a lista por usuário, buscada com o token de cada um."""
    client = TestClient(Platform(llm=provider()).app)

    ana = {m["id"] for m in client.get("/v1/models", headers=bearer(ANA_TOKEN)).json()["data"]}
    bia = {m["id"] for m in client.get("/v1/models", headers=bearer(BIA_TOKEN)).json()["data"]}

    assert "chefia" in bia and "chefia" not in ana
    assert "geral" in ana and "geral" in bia
    assert "privado" not in ana | bia, "Assistant só por chave de API não aparece para token OIDC"


def test_modo_nativo_de_ferramentas_e_recusado() -> None:
    client = TestClient(Platform(llm=provider()).app)
    tools = [{"type": "function", "function": {"name": "x", "parameters": {"type": "object"}}}]
    response = client.post("/v1/chat/completions", headers=headers(ANA_TOKEN), json=body(tools=tools))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "widening_field"


def test_conteudo_multimodal_e_recusado_em_messages() -> None:
    client = TestClient(Platform(llm=provider()).app)
    partes = [{"type": "text", "text": "o que é isto?"}, {"type": "image_url", "image_url": {"url": "data:,"}}]
    response = client.post(
        "/v1/chat/completions", headers=headers(ANA_TOKEN), json=body(messages=[{"role": "user", "content": partes}])
    )
    assert response.status_code == 400
    assert response.json()["error"]["param"] == "messages"
