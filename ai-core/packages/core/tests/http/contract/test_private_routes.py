"""T034 — operação pela superfície privada (US5; contracts/private-surface.md; clarificação 5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from http_testkit import ADMIN_KEY, ANA_TOKEN, SVC_KEY, Platform, bearer

from ai_core.http.adapters.development import StaticHealthProvider
from ai_core.http.ports import HealthItem


@pytest.fixture
def client() -> TestClient:
    return TestClient(Platform().app)


# --- packs (admin) ---------------------------------------------------------------------------------------------------


def test_admin_ve_packs_com_status_e_erro(client: TestClient) -> None:
    """US5 cen. 1: o registry falso das suítes tem `financeiro` em erro."""
    response = client.get("/private/v1/packs", headers=bearer(ADMIN_KEY))
    assert response.status_code == 200
    packs = {p["name"]: p for p in response.json()["data"]}
    assert packs["generic"]["status"] == "enabled" and packs["generic"]["error"] is None
    assert packs["financeiro"]["status"] == "error" and packs["financeiro"]["error"] == "contrato incompatível"
    assert set(packs["generic"]) == {"name", "version", "contract_version", "status", "error"}


def test_quem_nao_administra_recebe_404_nos_packs(client: TestClient) -> None:
    response = client.get("/private/v1/packs", headers=bearer(SVC_KEY))
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "recurso não encontrado"


# --- chaves (admin) --------------------------------------------------------------------------------------------------


def test_ciclo_de_chave_emitir_autenticar_listar_revogar(client: TestClient) -> None:
    """US5 cen. 2."""
    admin = bearer(ADMIN_KEY)
    emitida = client.post(
        "/private/v1/admin/keys", headers=admin, json={"subject": "svc:etl", "groups": ["leitores"], "label": "etl"}
    )
    assert emitida.status_code == 201
    chave, key_id = emitida.json()["key"], emitida.json()["key_id"]
    assert emitida.json()["subject"] == "svc:etl" and emitida.json()["groups"] == ["leitores"]

    assert client.get("/private/v1/models", headers=bearer(chave)).status_code == 200
    listadas = client.get("/private/v1/admin/keys", headers=admin).json()["data"]
    assert key_id in [k["key_id"] for k in listadas]
    assert chave not in str(listadas) and all("key" not in k for k in listadas)

    revogada = client.delete(f"/private/v1/admin/keys/{key_id}", headers=admin)
    assert revogada.status_code == 200 and revogada.json()["revoked_at"] is not None
    assert client.get("/private/v1/models", headers=bearer(chave)).status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("post", "/private/v1/admin/keys", {"subject": "svc:x"}),
        ("get", "/private/v1/admin/keys", None),
        ("delete", "/private/v1/admin/keys/00000000000000a1", None),
    ],
)
def test_quem_nao_administra_recebe_404_nas_chaves(client: TestClient, method: str, path: str, json: object) -> None:
    kwargs = {"headers": bearer(SVC_KEY)} | ({"json": json} if json is not None else {})
    assert getattr(client, method)(path, **kwargs).status_code == 404


def test_emissao_com_subject_invalido_ou_campo_desconhecido_e_400(client: TestClient) -> None:
    admin = bearer(ADMIN_KEY)
    invalido = client.post("/private/v1/admin/keys", headers=admin, json={"subject": "caio"})
    assert invalido.status_code == 400 and invalido.json()["error"]["param"] == "subject"
    extra = client.post("/private/v1/admin/keys", headers=admin, json={"subject": "svc:x", "admin": True})
    assert extra.status_code == 400 and extra.json()["error"]["param"] == "admin"


def test_revogar_chave_inexistente_e_404(client: TestClient) -> None:
    assert client.delete("/private/v1/admin/keys/00000000000000ff", headers=bearer(ADMIN_KEY)).status_code == 404


# --- saúde (qualquer chave) ------------------------------------------------------------------------------------------


def test_saude_responde_a_qualquer_chave(client: TestClient) -> None:
    """US5 cen. 3."""
    for key in (SVC_KEY, ADMIN_KEY):
        response = client.get("/private/v1/health", headers=bearer(key))
        assert response.status_code == 200 and response.json() == {"status": "ok", "items": []}


def test_saude_degradada_e_200_com_os_itens() -> None:
    """011 FR-012 (clarificação de 2026-09-30): item não crítico fora degrada, mas a instância atende o resto."""
    health = StaticHealthProvider(HealthItem(name="packs", ok=True), HealthItem(name="ollama", ok=False, detail="fora"))
    client = TestClient(Platform(health=health).app)
    response = client.get("/private/v1/health", headers=bearer(SVC_KEY))
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert {"name": "ollama", "ok": False, "critical": False, "detail": "fora"} in response.json()["items"]


def test_saude_com_item_critico_fora_e_503() -> None:
    health = StaticHealthProvider(
        HealthItem(name="database", ok=False, critical=True, detail="recusada"),
        HealthItem(name="ollama", ok=False, detail="fora"),
    )
    client = TestClient(Platform(health=health).app)
    response = client.get("/private/v1/health", headers=bearer(SVC_KEY))
    assert response.status_code == 503
    assert response.json()["status"] == "down"
    assert {"name": "database", "ok": False, "critical": True, "detail": "recusada"} in response.json()["items"]


def test_item_critico_saudavel_nao_derruba() -> None:
    health = StaticHealthProvider(HealthItem(name="database", ok=True, critical=True))
    response = TestClient(Platform(health=health).app).get("/private/v1/health", headers=bearer(SVC_KEY))
    assert response.status_code == 200 and response.json()["status"] == "ok"


def test_rotas_privadas_nao_existem_na_publica_nem_sem_credencial(client: TestClient) -> None:
    assert client.get("/v1/packs", headers=bearer(ANA_TOKEN)).status_code == 404
    assert client.get("/v1/health", headers=bearer(ANA_TOKEN)).status_code == 404
    assert client.get("/private/v1/health").status_code == 401
    assert client.get("/private/v1/health", headers=bearer(ANA_TOKEN)).status_code == 401
