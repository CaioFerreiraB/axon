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


def test_conteudo_multimodal_com_data_uri_invalido_e_recusado_nomeando_a_parte() -> None:
    """ADR-044, item 5: o anexo do Open WebUI chega em partes; data URI que não decodifica é 400 com o `param`."""
    client = TestClient(Platform(llm=provider()).app)
    partes = [{"type": "text", "text": "o que é isto?"}, {"type": "image_url", "image_url": {"url": "data:,"}}]
    response = client.post(
        "/v1/chat/completions", headers=headers(ANA_TOKEN), json=body(messages=[{"role": "user", "content": partes}])
    )
    assert response.status_code == 400
    assert response.json()["error"]["param"] == "messages[0].content[1].image_url.url"


# --- Fontes: cabeçalho `x-axon-citations` (FR-005b, ADR-051) ----------------------------------------------------------

CITACOES = (
    {
        "chunk_id": "por-2025#r13@p12",
        "document": "POR 2025",
        "version": "2.1",
        "status": "vigente",
        "section": "Regra 13",
        "page": 12,
        "url": "https://example.org/por.pdf#page=12",
    },
    {"chunk_id": "estatuto#art5@p3", "document": "Estatuto 2024", "page": 3, "url": "javascript:alert(1)"},
)


def _com_citacoes() -> Platform:
    from graph_testkit import ScriptedHooks, outcome

    return Platform(llm=provider(), hooks=ScriptedHooks(outcome=outcome(answer="Brasília [1] [2]", citations=CITACOES)))


def test_com_o_cabecalho_cada_citacao_vira_uma_fonte_do_open_webui_depois_do_texto() -> None:
    """FR-005b: um evento `source` por citação, na ordem do `[n]`, depois do último texto e antes do chunk final;
    id pelo `chunk_id`, legenda do ADR-026, página do Open WebUI (`page - 1`) e só URL `http(s)`."""
    client = TestClient(_com_citacoes().app)

    response = client.post("/v1/chat/completions", headers=headers(ANA_TOKEN), json=body())

    assert response.status_code == 200
    chunks = chunks_of(response.text)
    fontes = [(i, c["event"]["data"]) for i, c in enumerate(chunks) if c.get("event", {}).get("type") == "source"]
    assert [data["source"]["id"] for _, data in fontes] == ["por-2025#r13@p12", "estatuto#art5@p3"]
    ultimo_texto = max(i for i, c in enumerate(chunks) if c["choices"][0]["delta"].get("content"))
    assert all(ultimo_texto < i < len(chunks) - 1 for i, _ in fontes)
    assert all(chunks[i]["choices"][0]["delta"] == {} for i, _ in fontes)

    primeira, segunda = fontes[0][1], fontes[1][1]
    assert primeira["source"] == {
        "id": "por-2025#r13@p12",
        "name": "POR 2025 — Regra 13, p. 12",
        "url": "https://example.org/por.pdf#page=12",
    }
    assert primeira["metadata"] == [{"source": "por-2025#r13@p12", "name": "POR 2025 — Regra 13, p. 12", "page": 11}]
    assert primeira["document"] == [
        "Documento: POR 2025\n\nVersão: 2.1\n\nSituação: vigente\n\nSeção: Regra 13\n\nPágina: 12"
    ]
    assert segunda["source"] == {"id": "estatuto#art5@p3", "name": "Estatuto 2024, p. 3"}, "URL não http(s) não sai"
    assert chunks[-1]["x_axon"]["citations"][0]["url"] == "https://example.org/por.pdf#page=12"


def test_sem_o_cabecalho_de_citacoes_nenhuma_fonte_sai() -> None:
    client = TestClient(_com_citacoes().app)
    sem = {name: value for name, value in headers(ANA_TOKEN).items() if name != "x-axon-citations"}

    response = client.post("/v1/chat/completions", headers=sem, json=body())

    chunks = chunks_of(response.text)
    assert not any(c.get("event", {}).get("type") == "source" for c in chunks)
    assert [c["chunk_id"] for c in chunks[-1]["x_axon"]["citations"]] == ["por-2025#r13@p12", "estatuto#art5@p3"]


def test_sem_streaming_nenhuma_fonte_sai() -> None:
    client = TestClient(_com_citacoes().app)

    response = client.post("/v1/chat/completions", headers=headers(ANA_TOKEN), json=body(stream=False))

    assert response.status_code == 200
    assert "event" not in response.json()
    assert len(response.json()["x_axon"]["citations"]) == 2


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/chat"])
def test_modo_de_citacoes_desconhecido_e_400_nas_duas_entradas(path: str) -> None:
    client = TestClient(Platform(llm=provider()).app)
    payload = body() if path.endswith("completions") else {"assistant": "geral", "messages": body()["messages"]}
    errado = headers(ANA_TOKEN) | {"x-axon-citations": "links"}

    response = client.post(path, headers=errado, json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_header"
    assert response.json()["error"]["param"] == "x-axon-citations"
