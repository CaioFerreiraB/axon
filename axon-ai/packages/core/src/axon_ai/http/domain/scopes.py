"""Escopos da chave por rota (incremento 9.7; ADR-057 itens 1, 3, 5 e 8; research R66, R67).

Política pura: cada rota de `/private/v1` e `/admin/v1` declara um destes conjuntos, e as duas funções dizem se o
Principal entra. O OIDC não tem escopos (`None`) e continua regido pelo grupo.
"""

from __future__ import annotations

from typing import Final

from axon_ai.assistants.api import SCOPES, Scope

type RouteScopes = frozenset[Scope]

INFERENCE: Final[RouteScopes] = frozenset({"inference"})
"""Chat completions, `POST /chat`, `/models`, conversas e anexos."""
ACCOUNTS: Final[RouteScopes] = frozenset({"users", "admin"})
"""Contas, grupos e `GET /admin/v1/me`."""
ADMIN: Final[RouteScopes] = frozenset({"admin"})
"""O resto da administração e as rotas de administração da privada (padrão do decorador da administração)."""
ANY_KEY: Final[RouteScopes] = frozenset(SCOPES)
"""`/private/v1/health`."""


def key_reaches(scopes: frozenset[str] | None, route: frozenset[str]) -> bool:
    """A chave tem algum escopo da rota. `None` (OIDC) sempre passa aqui: quem o restringe é o grupo."""
    return scopes is None or bool(scopes & route)


def admin_access(scopes: frozenset[str] | None, route: frozenset[str], *, administers: bool) -> bool:
    """Quem entra numa rota de `/admin/v1` (R67). `administers` é a regra da 003 — o grupo e, com chave, o escopo
    `admin`. A chave `users` entra nas rotas que aceitam `users` sem o grupo; o grupo sem o escopo não entra."""
    if scopes is None:
        return administers
    return ("users" in route and "users" in scopes) or ("admin" in route and administers)
