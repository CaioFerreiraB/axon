"""Cabeçalhos com o nome Axon e a recusa dos antigos (US10 cenários 1, 3 e 5; FR-029 a FR-031; research R51, R55)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from graph_testkit import provider
from http_testkit import ANA_TOKEN, Platform, bearer

pytestmark = pytest.mark.us10

PERGUNTA = [{"role": "user", "content": "capital?"}]
ENTRADAS = [
    ("/v1/chat/completions", {"model": "geral", "messages": PERGUNTA}),
    ("/v1/chat", {"assistant": "geral", "messages": PERGUNTA}),
]
ANTIGOS = [
    ({"x-ai-core-store": "false"}, "x-ai-core-store", "x-axon-store"),
    ({"x-ai-core-progress": "status"}, "x-ai-core-progress", "x-axon-progress"),
    ({"x-ai-core-store": "false", "x-axon-store": "false"}, "x-ai-core-store", "x-axon-store"),
]


@pytest.mark.parametrize(("rota", "corpo"), ENTRADAS)
@pytest.mark.parametrize(("cabecalhos", "antigo", "novo"), ANTIGOS)
def test_cabecalho_antigo_e_recusado_antes_de_executar(
    rota: str, corpo: dict[str, Any], cabecalhos: dict[str, str], antigo: str, novo: str
) -> None:
    llm = provider()
    client = TestClient(Platform(llm=llm).app)
    response = client.post(rota, headers=bearer(ANA_TOKEN) | cabecalhos, json=corpo)
    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert (error["code"], error["param"]) == ("invalid_header", antigo)
    assert novo in error["message"]
    assert llm.calls == []


@pytest.mark.parametrize(("rota", "corpo"), ENTRADAS)
def test_so_o_cabecalho_novo_torna_o_pedido_efemero(rota: str, corpo: dict[str, Any]) -> None:
    client = TestClient(Platform(llm=provider()).app)
    response = client.post(rota, headers=bearer(ANA_TOKEN) | {"x-axon-store": "false"}, json=corpo)
    assert response.status_code == 200, response.text
    assert "x-conversation-id" not in response.headers


def test_o_documento_openapi_se_chama_axon() -> None:
    client = TestClient(Platform(llm=provider()).app)
    assert client.get("/openapi.json").json()["info"]["title"] == "Axon"
