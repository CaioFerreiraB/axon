"""T139 — apagar uma conta e um grupo de cada vez pela administração (incremento 9.7, US13 cen. 6 a 8; FR-049, FR-050;
research R68, R69; clarificação Q1)."""

from __future__ import annotations

import json

import pytest
from scopes_kit import ADMIN_KEY, CONSOLE_ROOT, OPERATOR_KEY, USERS_KEY, Eraser, scopes_kit

from axon_ai.identity.api import AccountNotFound

pytestmark = pytest.mark.us13


@pytest.mark.parametrize("token", [USERS_KEY, ADMIN_KEY, CONSOLE_ROOT])
def test_cen_6_apaga_e_devolve_o_relatorio(token: str) -> None:
    kit = scopes_kit(erasers=(Eraser("conversas"),))

    response = kit.admin("DELETE", "/users/ana", token)

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["username"] == "ana" and report["complete"] is True
    assert report["identity"]["account"] == 1
    assert report["modules"] == [{"name": "conversas", "counts": {"conversations": 1}, "warnings": [], "failed": False}]
    assert "deleted:" not in json.dumps(report), "o relatório nunca traz o pseudônimo (ADR-059)"
    with pytest.raises(AccountNotFound):
        kit.account("ana")
    assert kit.admin("GET", "/users/ana", token).status_code == 404


def test_cen_6_propria_conta_e_inexistente() -> None:
    kit = scopes_kit()
    for token in (CONSOLE_ROOT, ADMIN_KEY):  # a chave de `user:root` também é a própria conta
        propria = kit.admin("DELETE", "/users/root", token)
        assert propria.status_code == 422 and propria.json()["error"]["param"] == "username"
    assert kit.admin("DELETE", "/users/ninguem", CONSOLE_ROOT).status_code == 404


def test_cen_6_ultimo_admin_ativo_e_409() -> None:
    kit = scopes_kit()
    assert kit.admin("POST", "/users/root/disable", OPERATOR_KEY).status_code == 200

    response = kit.admin("DELETE", "/users/chefe", OPERATOR_KEY)

    assert response.status_code == 409 and response.json()["error"]["code"] == "protected_group"
    assert kit.account("chefe").active


def test_cen_7_apagamento_incompleto_e_503_e_repetir_retoma() -> None:
    kit = scopes_kit(erasers=(Eraser("conversas", fail=1),))

    falha = kit.admin("DELETE", "/users/ana", CONSOLE_ROOT)

    assert falha.status_code == 503, falha.text
    assert falha.headers["retry-after"] == "5"
    corpo = falha.json()
    assert corpo["error"]["code"] == "deletion_incomplete"
    assert corpo["report"]["complete"] is False
    assert corpo["report"]["modules"][0]["failed"] is True
    assert "deleted:" not in falha.text

    repetido = kit.admin("DELETE", "/users/ana", CONSOLE_ROOT)
    assert repetido.status_code == 200 and repetido.json()["complete"] is True


def test_cen_8_um_grupo_de_cada_vez() -> None:
    kit = scopes_kit()
    kit.admin("POST", "/groups", USERS_KEY, {"name": "monitores"})

    for _ in range(2):
        posto = kit.admin("PUT", "/users/ana/groups/monitores", USERS_KEY)
        assert posto.status_code == 200 and posto.json()["groups"] == ["equipe", "monitores"]
    for _ in range(2):
        tirado = kit.admin("DELETE", "/users/ana/groups/monitores", USERS_KEY)
        assert tirado.status_code == 200 and tirado.json()["groups"] == ["equipe"]

    assert kit.admin("PUT", "/users/ana/groups/inexistente", USERS_KEY).status_code == 404
    assert kit.admin("DELETE", "/users/ana/groups/inexistente", USERS_KEY).status_code == 404
    assert kit.admin("PUT", "/users/ninguem/groups/equipe", USERS_KEY).status_code == 404
    com_corpo = kit.admin("PUT", "/users/ana/groups/equipe", USERS_KEY, {"version": 1})
    assert com_corpo.status_code == 422


def test_t152_a_conta_em_apagamento_traz_deleting() -> None:
    """008 FR-054 (R72): depois de um apagamento incompleto, a visão da conta diz que ela está em apagamento."""
    kit = scopes_kit(erasers=(Eraser("conversas", fail=1),))
    assert kit.admin("GET", "/users/ana", CONSOLE_ROOT).json()["deleting"] is False

    assert kit.admin("DELETE", "/users/ana", CONSOLE_ROOT).status_code == 503

    assert kit.admin("GET", "/users/ana", CONSOLE_ROOT).json()["deleting"] is True
    lista = {a["username"]: a["deleting"] for a in kit.admin("GET", "/users?state=all", CONSOLE_ROOT).json()["data"]}
    assert lista["ana"] is True and lista["root"] is False
