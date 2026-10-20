"""T068 — pedido efêmero com `x-axon-store: false` (FR-023, FR-014; contracts/chat-completions.md, "Fase 7")."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from graph_testkit import provider
from http_testkit import ADMIN_KEY, ANA_TOKEN, CAIO_TOKEN, Platform, bearer, chunks_of

pytestmark = pytest.mark.us8

EFEMERO = {"x-axon-store": "false"}
PERGUNTA = [{"role": "user", "content": "capital?"}]


def compat(*, stream: bool = False, **extra: Any) -> dict[str, Any]:
    return {"model": "geral", "messages": PERGUNTA, "stream": stream} | extra


def conversas(client: TestClient, token: str) -> list[Any]:
    return client.get("/v1/conversations", headers=bearer(token)).json()["data"]


@pytest.mark.parametrize(
    ("rota", "credencial", "corpo"),
    [
        ("/v1/chat/completions", ANA_TOKEN, compat()),
        ("/v1/chat/completions", ANA_TOKEN, compat(stream=True)),
        ("/private/v1/chat/completions", ADMIN_KEY, compat()),
        ("/private/v1/chat/completions", ADMIN_KEY, compat(stream=True)),
        ("/v1/chat", ANA_TOKEN, {"assistant": "geral", "messages": PERGUNTA}),
        ("/v1/chat", ANA_TOKEN, {"assistant": "geral", "messages": PERGUNTA, "stream": True}),
    ],
)
def test_pedido_efemero_nao_cria_conversa_nem_devolve_id(rota: str, credencial: str, corpo: dict[str, Any]) -> None:
    client = TestClient(Platform(llm=provider()).app)
    response = client.post(rota, headers=bearer(credencial) | EFEMERO, json=corpo)

    assert response.status_code == 200
    assert "x-conversation-id" not in response.headers
    if corpo.get("stream"):
        chunks = chunks_of(response.text)
        assert all("conversation_id" not in c.get("x_axon", {}) for c in chunks)
        assert "".join(c["choices"][0]["delta"].get("content", "") for c in chunks) == "Brasília"
    else:
        assert "conversation_id" not in response.json()["x_axon"]
        assert response.json()["choices"][0]["message"]["content"] == "Brasília"
    # A conversa é do subject: `user:caio` (a `ADMIN_KEY`) lê as suas pela superfície pública com o próprio token.
    assert conversas(client, ANA_TOKEN if credencial == ANA_TOKEN else CAIO_TOKEN) == []


def test_sem_o_cabecalho_a_conversa_nasce_como_antes() -> None:
    """Regressão do FR-013: o cabeçalho é opt-in."""
    client = TestClient(Platform(llm=provider()).app)
    response = client.post("/v1/chat/completions", headers=bearer(ANA_TOKEN), json=compat())
    assert response.headers["x-conversation-id"]
    assert len(conversas(client, ANA_TOKEN)) == 1


def test_true_grava_normalmente() -> None:
    client = TestClient(Platform(llm=provider()).app)
    headers = bearer(ANA_TOKEN) | {"x-axon-store": "true"}
    response = client.post("/v1/chat/completions", headers=headers, json=compat())
    assert response.headers["x-conversation-id"]


def test_efemero_com_id_de_conversa_e_conflito_antes_de_executar() -> None:
    llm = provider()
    client = TestClient(Platform(llm=llm).app)
    cid = client.post("/v1/chat/completions", headers=bearer(ANA_TOKEN), json=compat()).headers["x-conversation-id"]
    chamadas = len(llm.calls)

    response = client.post(
        "/v1/chat/completions", headers=bearer(ANA_TOKEN) | EFEMERO, json=compat(conversation_id=cid)
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "store_conflict"
    assert response.json()["error"]["param"] == "x-axon-store"
    assert len(llm.calls) == chamadas, "nenhuma execução"


def test_valor_desconhecido_e_recusado_nomeando_o_cabecalho() -> None:
    client = TestClient(Platform(llm=provider()).app)
    response = client.post(
        "/v1/chat/completions", headers=bearer(ANA_TOKEN) | {"x-axon-store": "talvez"}, json=compat()
    )
    assert response.status_code == 400
    assert (response.json()["error"]["code"], response.json()["error"]["param"]) == (
        "invalid_header",
        "x-axon-store",
    )
