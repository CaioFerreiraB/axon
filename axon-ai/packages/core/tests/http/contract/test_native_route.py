"""T030 — `POST /v1/chat` e `/private/v1/chat` (US3): recusa antes de executar, mesma resposta da compat (R17, R18)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from graph_testkit import provider
from http_testkit import ADMIN_KEY, ANA_TOKEN, Platform, answer_of, bearer, chunks_of, has_done

from axon_ai.assistants.api import WIDENING_FIELDS

MENSAGENS = [{"role": "user", "content": "qual é a capital?"}]


@pytest.mark.parametrize("field", ["mcp_servers", "packs", "tools", "provider", "collections"])
def test_ampliacao_recusada_nomeando_o_campo_sem_executar(field: str) -> None:
    """US3 cen. 1."""
    llm = provider()
    client = TestClient(Platform(llm=llm).app)
    response = client.post(
        "/v1/chat", headers=bearer(ANA_TOKEN), json={"assistant": "geral", "messages": MENSAGENS, field: ["x"]}
    )
    assert response.status_code == 400
    assert response.json()["error"]["param"] == field and response.json()["error"]["code"] == "widening_field"
    assert llm.calls == []


def test_campo_desconhecido_recusado() -> None:
    client = TestClient(Platform().app)
    response = client.post(
        "/v1/chat", headers=bearer(ANA_TOKEN), json={"assistant": "geral", "messages": MENSAGENS, "temperature": 0}
    )
    assert response.status_code == 400 and response.json()["error"]["param"] == "temperature"


def test_resposta_igual_a_da_compat_sem_streaming() -> None:
    client = TestClient(Platform().app)
    nativa = client.post("/v1/chat", headers=bearer(ANA_TOKEN), json={"assistant": "geral", "messages": MENSAGENS})
    assert nativa.status_code == 200
    assert nativa.json()["object"] == "chat.completion"
    assert nativa.json()["choices"][0]["message"]["content"] == "Brasília"


def test_resposta_igual_a_da_compat_em_streaming_na_privada() -> None:
    client = TestClient(Platform().app)
    response = client.post(
        "/private/v1/chat",
        headers=bearer(ADMIN_KEY),
        json={"assistant": "privado", "messages": MENSAGENS, "stream": True},
    )
    assert response.status_code == 200 and has_done(response.text)
    assert answer_of(chunks_of(response.text)) == "Brasília"


def test_restricao_de_modelo_fora_da_allowlist_recusada_antes_de_executar() -> None:
    llm = provider()
    client = TestClient(Platform(llm=llm).app)
    response = client.post(
        "/v1/chat",
        headers=bearer(ANA_TOKEN),
        json={"assistant": "geral", "model": "openai/gpt-x", "messages": MENSAGENS},
    )
    assert response.status_code == 400 and response.json()["error"]["code"] == "model_not_allowed"
    assert llm.calls == []


@pytest.mark.parametrize("field", sorted(WIDENING_FIELDS))
def test_compat_tambem_recusa_a_lista_da_003(field: str) -> None:
    """R18: uma lista só para a regra de ampliação."""
    client = TestClient(Platform().app)
    response = client.post(
        "/v1/chat/completions",
        headers=bearer(ANA_TOKEN),
        json={"model": "geral", "messages": MENSAGENS, field: ["x"]},
    )
    assert response.status_code == 400 and response.json()["error"]["param"] == field
