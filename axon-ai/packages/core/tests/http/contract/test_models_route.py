"""T028 — `/v1/models` e `/private/v1/models` (US2; contracts/models.md): a listagem é o que o Principal resolve."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from http_testkit import ADMIN_KEY, ANA_TOKEN, BIA_TOKEN, CREATED, SVC_KEY, Platform, bearer

from axon_ai.llm.api import ModelRef


def _ids(client: TestClient, token: str, prefix: str = "/v1") -> list[str]:
    response = client.get(f"{prefix}/models", headers=bearer(token))
    assert response.status_code == 200
    return [entry["id"] for entry in response.json()["data"]]


@pytest.fixture
def client() -> TestClient:
    return TestClient(Platform().app)


def test_listas_diferem_exatamente_pela_acl(client: TestClient) -> None:
    """US2 cen. 1: `geral` é público; `chefia` só para o grupo; `privado` só para `user:caio` por chave."""
    assert _ids(client, ANA_TOKEN) == ["geral"]
    assert _ids(client, BIA_TOKEN) == ["chefia", "geral"]
    assert _ids(client, ADMIN_KEY, "/private/v1") == ["geral", "privado"]
    assert _ids(client, SVC_KEY, "/private/v1") == ["geral"]


def test_formato_da_entrada(client: TestClient) -> None:
    (entrada,) = client.get("/v1/models", headers=bearer(ANA_TOKEN)).json()["data"]
    assert entrada == {
        "id": "geral",
        "object": "model",
        "created": int(CREATED.timestamp()),
        "owned_by": "system",
        "x_ai_core": {
            "generation": str(ModelRef(provider="ollama", model="qwen3:1.7b")),
            "description": "uso geral",
            "origin": "system",
            "allow": ["ollama/*"],
        },
    }
    assert client.get("/v1/models", headers=bearer(ANA_TOKEN)).json()["object"] == "list"


def test_id_listado_resolve_no_chat(client: TestClient) -> None:
    for model in _ids(client, BIA_TOKEN):
        response = client.post(
            "/v1/chat/completions",
            headers=bearer(BIA_TOKEN),
            json={"model": model, "messages": [{"role": "user", "content": "oi"}]},
        )
        assert response.status_code == 200, model


def test_privado_usado_por_quem_nao_pode_e_igual_a_inexistente(client: TestClient) -> None:
    """US2 cen. 2."""

    def post(model: str) -> Any:
        return client.post(
            "/v1/chat/completions",
            headers=bearer(ANA_TOKEN),
            json={"model": model, "messages": [{"role": "user", "content": "oi"}]},
        )

    privado, inexistente = post("chefia"), post("nao-existe")
    assert privado.status_code == inexistente.status_code == 404
    assert privado.json() == inexistente.json()


def test_indisponivel_nao_aparece() -> None:
    from assistants_testkit import assistant, config

    client = TestClient(Platform(config({"geral": assistant(), "quebrado": assistant(packs=["financeiro"])})).app)
    assert _ids(client, ANA_TOKEN) == ["geral"]


def test_sem_credencial_e_401_no_envelope(client: TestClient) -> None:
    response = client.get("/v1/models")
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"
