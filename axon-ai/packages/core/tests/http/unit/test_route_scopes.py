"""T137 — toda rota de `/private/v1` e `/admin/v1` declara os escopos que a alcançam (SC-012; research R66).

Percorre as rotas montadas: uma rota nova sem declaração falha aqui, não em produção (ADR-057 item 8).
"""

from __future__ import annotations

import pytest
from scopes_kit import MountedRoute, mounted_routes, scopes_kit

from axon_ai.http.domain.scopes import ACCOUNTS, ADMIN, ANY_KEY, INFERENCE

pytestmark = pytest.mark.us13

PREFIXES = ("/private/v1", "/admin/v1")


def _expected(path: str) -> frozenset[str]:
    if path.startswith("/private/v1"):
        rest = path.removeprefix("/private/v1")
        if rest == "/health":
            return ANY_KEY
        if rest.startswith(("/packs", "/admin/keys", "/mcp")):
            return ADMIN
        return INFERENCE
    rest = path.removeprefix("/admin/v1")
    if rest == "/me" or rest.startswith(("/users", "/groups")):
        return ACCOUNTS
    return ADMIN


def _routes() -> list[MountedRoute]:
    return mounted_routes(scopes_kit().platform.app, *PREFIXES)


def test_toda_rota_declara_os_escopos() -> None:
    routes = _routes()
    assert len(routes) > 40, "a enumeração precisa achar as rotas das duas superfícies"
    assert [f"{route.method} {route.path}" for route in routes if route.scopes is None] == []


def test_os_escopos_batem_com_a_tabela() -> None:
    errados = {
        f"{route.method} {route.path}": sorted(route.scopes)
        for route in _routes()
        if route.scopes is not None and route.scopes != _expected(route.path)
    }
    assert errados == {}


def test_as_rotas_esperadas_estao_montadas() -> None:
    paths = {route.path for route in _routes()}
    for path in (
        "/private/v1/chat/completions",
        "/private/v1/chat",
        "/private/v1/models",
        "/private/v1/conversations",
        "/private/v1/packs",
        "/private/v1/admin/keys",
        "/private/v1/health",
        "/admin/v1/me",
        "/admin/v1/users/{username}",
        "/admin/v1/users/{username}/groups/{group}",
        "/admin/v1/prices",
    ):
        assert path in paths, path
