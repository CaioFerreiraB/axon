"""T140 — a chave `users` não escala (SC-013; incremento 9.7, US13 cen. 3; FR-048; achados C1 da 003 e C1/U1 da
008). Cada escrita que toca o grupo de administração ou uma conta dele responde 403 nomeando o campo, e nada muda; toda
outra rota de `/admin/v1` responde 404; e a chave `inference` recebe 404 em todas."""

from __future__ import annotations

import re
from typing import Any

import pytest
from scopes_kit import ADMIN, CONSOLE_ROOT, INFERENCE_KEY, USERS_KEY, Kit, mounted_routes, scopes_kit

from axon_ai.http.domain.scopes import ACCOUNTS

pytestmark = pytest.mark.us13


def _version(kit: Kit, username: str) -> int:
    return int(kit.admin("GET", f"/users/{username}", CONSOLE_ROOT).json()["version"])


def _snapshot(kit: Kit) -> Any:
    users = kit.admin("GET", "/users?state=all", CONSOLE_ROOT).json()["data"]
    groups = kit.admin("GET", "/groups", CONSOLE_ROOT).json()["data"]
    return users, groups


def _escaladas(kit: Kit) -> list[tuple[str, str, Any, str]]:
    return [
        ("POST", "/users", {"username": "eva", "email": "eva@x.org", "name": "Eva", "groups": [ADMIN]}, "groups"),
        ("PATCH", "/users/root", {"name": "Outro", "version": _version(kit, "root")}, "username"),
        ("PATCH", "/users/ana", {"groups": ["equipe", ADMIN], "version": _version(kit, "ana")}, "groups"),
        ("POST", "/users/root/password", None, "username"),
        ("POST", "/users/root/disable", None, "username"),
        ("POST", "/users/root/enable", None, "username"),
        ("DELETE", "/users/root/google", None, "username"),
        ("DELETE", "/users/root", None, "username"),
        ("PUT", f"/users/ana/groups/{ADMIN}", None, "group"),
        ("DELETE", f"/users/chefe/groups/{ADMIN}", None, "group"),
        ("PUT", "/users/root/groups/equipe", None, "username"),
        ("DELETE", "/users/chefe/groups/equipe", None, "username"),
        ("PUT", f"/groups/{ADMIN}/members", {"usernames": ["root", "chefe", "ana"]}, "name"),
        ("PUT", "/groups/equipe/members", {"usernames": ["ana"]}, "members"),
    ]


def test_toda_escalada_e_403_e_nada_muda() -> None:
    kit = scopes_kit()
    antes = _snapshot(kit)

    recusas = {}
    for method, path, body, _field in _escaladas(kit):
        response = kit.admin(method, path, USERS_KEY, body)
        error = response.json().get("error", {})
        recusas[f"{method} {path}"] = (response.status_code, error.get("code"), error.get("param"))

    esperado = {f"{m} {p}": (403, "actor_not_allowed", f) for m, p, _b, f in _escaladas(kit)}
    assert recusas == esperado
    # Apagar o grupo de administração é recusado a todos, antes da regra do ator (012 FR-011): 409, e nada muda.
    protegido = kit.admin("DELETE", f"/groups/{ADMIN}", USERS_KEY)
    assert (protegido.status_code, protegido.json()["error"]["code"]) == (409, "protected_group")
    assert _snapshot(kit) == antes


def _admin_routes(kit: Kit) -> list[tuple[str, str, frozenset[str]]]:
    return [
        (route.method, re.sub(r"\{[^}]+\}", "x", route.path), route.scopes or frozenset())
        for route in mounted_routes(kit.platform.app, "/admin/v1")
    ]


def test_users_recebe_404_em_toda_rota_fora_de_contas() -> None:
    kit = scopes_kit()
    fora = [(m, p) for m, p, scopes in _admin_routes(kit) if scopes != ACCOUNTS]
    assert len(fora) > 20, "a enumeração precisa achar as rotas da administração"

    respostas = {f"{m} {p}": kit.call(m, p, USERS_KEY, {} if m != "GET" else None).status_code for m, p in fora}

    assert {rota: status for rota, status in respostas.items() if status != 404} == {}


def test_inference_recebe_404_em_toda_rota_da_administracao() -> None:
    kit = scopes_kit()
    rotas = [(m, p) for m, p, _scopes in _admin_routes(kit)]

    respostas = {f"{m} {p}": kit.call(m, p, INFERENCE_KEY, {} if m != "GET" else None).status_code for m, p in rotas}

    assert {rota: status for rota, status in respostas.items() if status != 404} == {}
