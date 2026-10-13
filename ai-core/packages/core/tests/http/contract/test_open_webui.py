"""T069 — o pedido do Open WebUI v0.12 (US8 cen. 1 e 2; contracts/open-webui.md, verificações 1 e 2; research R38)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from graph_testkit import provider
from http_testkit import ANA_TOKEN, BIA_TOKEN, Platform, bearer, chunks_of, has_done
from open_webui_v0_12 import body, headers

pytestmark = pytest.mark.us8


def test_pedido_do_open_webui_recebe_streaming_com_raciocinio_antes_do_texto() -> None:
    client = TestClient(Platform(llm=provider()).app)

    response = client.post("/v1/chat/completions", headers=headers(ANA_TOKEN), json=body())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "x-conversation-id" not in response.headers
    chunks = chunks_of(response.text)
    deltas = [c["choices"][0]["delta"] for c in chunks]
    primeiro_texto = next(i for i, d in enumerate(deltas) if d.get("content"))
    assert any(d.get("reasoning_content") for d in deltas[:primeiro_texto]), "progresso visível antes da resposta"
    assert not any(d.get("reasoning_content") for d in deltas[primeiro_texto:])
    assert all(d.get("reasoning_content", "\n").endswith("\n") for d in deltas)
    assert "".join(d.get("content", "") for d in deltas) == "Brasília"
    assert all("conversation_id" not in c.get("x_ai_core", {}) for c in chunks)
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert has_done(response.text)


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
