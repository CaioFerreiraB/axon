"""T032 — CRUD de Assistants de usuário na superfície pública (US4; contracts/user-assistants.md)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from http_testkit import ADMIN_KEY, ANA_TOKEN, BIA_TOKEN, Platform, bearer

MENSAGENS = [{"role": "user", "content": "oi"}]


def rascunho(name: str = "meu-rag", **overrides: Any) -> dict[str, Any]:
    return {"name": name, "packs": ["generic"], "models": {"generation": "ollama/qwen3:1.7b"}} | overrides


@pytest.fixture
def client() -> TestClient:
    return TestClient(Platform().app)


def test_ciclo_completo_pela_superficie_publica(client: TestClient) -> None:
    ana = bearer(ANA_TOKEN)
    criado = client.post("/v1/assistants", headers=ana, json=rascunho(description="v1"))
    assert criado.status_code == 201
    assert criado.json()["name"] == "~meu-rag" and criado.json()["owner"] == "user:ana"
    assert criado.json()["status"] == {"available": True, "reasons": []}

    assert client.get("/v1/assistants/~meu-rag", headers=ana).json()["draft"]["description"] == "v1"
    atualizado = client.put("/v1/assistants/meu-rag", headers=ana, json=rascunho(description="v2"))
    assert atualizado.status_code == 200 and atualizado.json()["draft"]["description"] == "v2"
    assert [a["name"] for a in client.get("/v1/assistants", headers=ana).json()["data"]] == ["~meu-rag"]

    assert client.delete("/v1/assistants/~meu-rag", headers=ana).status_code == 204
    assert client.get("/v1/assistants/~meu-rag", headers=ana).status_code == 404
    assert client.get("/v1/assistants", headers=ana).json()["data"] == []


def test_criado_aparece_nos_modelos_do_dono_e_resolve_no_chat(client: TestClient) -> None:
    """US4 cen. 2."""
    client.post("/v1/assistants", headers=bearer(ANA_TOKEN), json=rascunho())
    ids = [m["id"] for m in client.get("/v1/models", headers=bearer(ANA_TOKEN)).json()["data"]]
    assert "~meu-rag" in ids
    assert "~meu-rag" not in [m["id"] for m in client.get("/v1/models", headers=bearer(BIA_TOKEN)).json()["data"]]
    chat = client.post(
        "/v1/chat/completions", headers=bearer(ANA_TOKEN), json={"model": "~meu-rag", "messages": MENSAGENS}
    )
    assert chat.status_code == 200


def test_outro_usuario_recebe_404(client: TestClient) -> None:
    client.post("/v1/assistants", headers=bearer(ANA_TOKEN), json=rascunho())
    bia = bearer(BIA_TOKEN)
    assert client.get("/v1/assistants/~meu-rag", headers=bia).status_code == 404
    assert client.put("/v1/assistants/~meu-rag", headers=bia, json=rascunho()).status_code == 404
    assert client.delete("/v1/assistants/~meu-rag", headers=bia).status_code == 404


def test_fora_da_politica_e_400_com_o_campo(client: TestClient) -> None:
    response = client.post(
        "/v1/assistants", headers=bearer(ANA_TOKEN), json=rascunho(models={"generation": "openai/gpt-4o"})
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "policy_violation"
    assert response.json()["error"]["param"] == "models.generation"


def test_sem_politica_aplicavel_e_400() -> None:
    from assistants_testkit import assistant, config, policy

    client = TestClient(Platform(config({"geral": assistant()}, policies=[policy(match="group:chefia")])).app)
    response = client.post("/v1/assistants", headers=bearer(ANA_TOKEN), json=rascunho())
    assert response.status_code == 400 and response.json()["error"]["code"] == "no_applicable_policy"


def test_nome_repetido_e_409(client: TestClient) -> None:
    client.post("/v1/assistants", headers=bearer(ANA_TOKEN), json=rascunho())
    response = client.post("/v1/assistants", headers=bearer(ANA_TOKEN), json=rascunho())
    assert response.status_code == 409 and response.json()["error"]["code"] == "conflict"


def test_corpo_com_campo_desconhecido_e_400(client: TestClient) -> None:
    response = client.post("/v1/assistants", headers=bearer(ANA_TOKEN), json=rascunho(visibility="public"))
    assert response.status_code == 400 and response.json()["error"]["param"] == "visibility"


def test_rotas_nao_existem_na_superficie_privada(client: TestClient) -> None:
    """FR-006: CRUD de Assistants de usuário é da superfície pública."""
    assert client.get("/private/v1/assistants", headers=bearer(ADMIN_KEY)).status_code == 404
    assert client.post("/private/v1/assistants", headers=bearer(ADMIN_KEY), json=rascunho()).status_code in {404, 405}
