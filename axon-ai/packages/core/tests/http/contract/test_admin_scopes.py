"""T138 — quem entra em cada rota pelo escopo da chave (incremento 9.7, US13 cen. 1, 2, 4, 5 e 9; FR-046, FR-047,
FR-051, FR-052; research R66, R67, R70)."""

from __future__ import annotations

from typing import Any

import pytest
from http_testkit import body
from scopes_kit import ADMIN, ADMIN_KEY, CONSOLE_ROOT, GROUP_ONLY_KEY, INFERENCE_KEY, USERS_KEY, Kit, scopes_kit

pytestmark = pytest.mark.us13


@pytest.fixture
def kit() -> Kit:
    return scopes_kit()


def _not_found(response: Any) -> None:
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "not_found"


# --- cen. 1: a chave `users` -----------------------------------------------------------------------------------------


def test_cen_1_users_le_tudo_inclusive_a_administracao(kit: Kit) -> None:
    usuarios = kit.admin("GET", "/users?state=all", USERS_KEY)
    assert usuarios.status_code == 200
    assert {"root", "chefe", "ana"} <= {a["username"] for a in usuarios.json()["data"]}
    assert kit.admin("GET", "/users/root", USERS_KEY).json()["groups"] == [ADMIN]
    grupos = {g["name"]: g for g in kit.admin("GET", "/groups", USERS_KEY).json()["data"]}
    assert grupos[ADMIN]["protected"] is True


def test_cen_1_users_cria_e_agrupa_fora_da_administracao(kit: Kit) -> None:
    criada = kit.admin(
        "POST",
        "/users",
        USERS_KEY,
        {"username": "bia", "email": "bia@exemplo.org", "name": "Bia", "groups": ["equipe"]},
    )
    assert criada.status_code == 201, criada.text
    assert kit.admin("POST", "/groups", USERS_KEY, {"name": "monitores"}).status_code == 201
    assert kit.admin("PUT", "/users/bia/groups/monitores", USERS_KEY).json()["groups"] == ["equipe", "monitores"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/admin/v1/keys"),
        ("POST", "/admin/v1/keys"),
        ("GET", "/admin/v1/prices"),
        ("GET", "/admin/v1/usage"),
        ("GET", "/admin/v1/impact"),
        ("GET", "/admin/v1/observability"),
        ("GET", "/admin/v1/assistants"),
        ("GET", "/admin/v1/health"),
        ("GET", "/admin/v1/login-settings"),
        ("GET", "/admin/v1/mcp"),
        ("GET", "/private/v1/models"),
        ("GET", "/private/v1/conversations"),
        ("GET", "/private/v1/packs"),
        ("GET", "/private/v1/admin/keys"),
        ("GET", "/private/v1/mcp"),
    ],
)
def test_cen_1_users_nao_alcanca_o_resto(kit: Kit, method: str, path: str) -> None:
    """O 404 vem antes de qualquer seam: os seams de fora de contas são `Untouchable`."""
    _not_found(kit.call(method, path, USERS_KEY, {} if method == "POST" else None))


def test_cen_1_users_nao_conversa(kit: Kit) -> None:
    _not_found(kit.call("POST", "/private/v1/chat/completions", USERS_KEY, body(model="geral")))


def test_a_saude_da_privada_vale_para_qualquer_chave(kit: Kit) -> None:
    assert kit.call("GET", "/private/v1/health", USERS_KEY).status_code in (200, 503)


# --- cen. 2: a chave `inference` -------------------------------------------------------------------------------------


def test_cen_2_inference_conversa(kit: Kit) -> None:
    assert kit.call("POST", "/private/v1/chat/completions", INFERENCE_KEY, body(model="geral")).status_code == 200
    assert [m["id"] for m in kit.call("GET", "/private/v1/models", INFERENCE_KEY).json()["data"]] == ["geral"]
    assert kit.call("GET", "/private/v1/conversations", INFERENCE_KEY).status_code == 200


@pytest.mark.parametrize(
    "path", ["/admin/v1/users", "/admin/v1/me", "/admin/v1/groups", "/private/v1/packs", "/private/v1/admin/keys"]
)
def test_cen_2_inference_nao_administra(kit: Kit, path: str) -> None:
    _not_found(kit.call("GET", path, INFERENCE_KEY))


# --- cen. 9: o grupo sem o escopo ------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/admin/v1/users", "/admin/v1/me", "/admin/v1/assistants", "/private/v1/packs"])
def test_cen_9_grupo_sem_escopo_nao_administra(kit: Kit, path: str) -> None:
    _not_found(kit.call("GET", path, GROUP_ONLY_KEY))


def test_o_admin_com_escopo_alcanca_tudo(kit: Kit) -> None:
    assert kit.admin("GET", "/users", ADMIN_KEY).status_code == 200
    assert kit.admin("GET", "/assistants", ADMIN_KEY).status_code == 200
    assert kit.call("GET", "/private/v1/packs", ADMIN_KEY).status_code == 200


# --- cen. 4: emissão e visão -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/admin/v1/keys", "/private/v1/admin/keys"])
def test_cen_4_emissao_com_escopos(kit: Kit, prefix: str) -> None:
    com = kit.call("POST", prefix, ADMIN_KEY, {"subject": "svc:prov", "scopes": ["users"]})
    assert com.status_code == 201, com.text
    assert com.json()["scopes"] == ["users"]
    sem = kit.call("POST", prefix, ADMIN_KEY, {"subject": "svc:app"})
    assert sem.json()["scopes"] == ["inference"]
    dois = kit.call("POST", prefix, ADMIN_KEY, {"subject": "svc:ambos", "scopes": ["users", "inference"]})
    assert dois.json()["scopes"] == ["inference", "users"]


@pytest.mark.parametrize("prefix", ["/admin/v1/keys", "/private/v1/admin/keys"])
@pytest.mark.parametrize("scopes", [["admin"], ["desconhecido"], [], "users"])
def test_cen_4_escopos_recusados(kit: Kit, prefix: str, scopes: Any) -> None:
    response = kit.call("POST", prefix, ADMIN_KEY, {"subject": "svc:prov", "scopes": scopes})
    assert response.status_code in (400, 422), response.text
    assert response.json()["error"]["param"] == "scopes"


def test_cen_4_a_listagem_e_a_rotacao_mostram_os_escopos(kit: Kit) -> None:
    listagem = {k["key_id"]: k["scopes"] for k in kit.admin("GET", "/keys", ADMIN_KEY).json()["data"]}
    assert listagem["00000000000000c3"] == ["users"]
    assert listagem["00000000000000e5"] == ["admin", "inference"]
    privada = {k["key_id"]: k["scopes"] for k in kit.call("GET", "/private/v1/admin/keys", ADMIN_KEY).json()["data"]}
    assert privada == listagem
    rotacionada = kit.admin("POST", "/keys/00000000000000c3/rotate", ADMIN_KEY)
    assert rotacionada.status_code == 200 and rotacionada.json()["scopes"] == ["users"]


# --- cen. 5: `me` ----------------------------------------------------------------------------------------------------


def test_cen_5_me_traz_os_escopos(kit: Kit) -> None:
    assert kit.admin("GET", "/me", USERS_KEY).json()["scopes"] == ["users"]
    assert kit.admin("GET", "/me", ADMIN_KEY).json()["scopes"] == ["admin", "inference"]
    console = kit.admin("GET", "/me", CONSOLE_ROOT).json()
    assert console["scopes"] is None and console["subject"] == "user:root"
