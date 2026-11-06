"""T136 — as regras puras do escopo por rota (incremento 9.7, US13; research R66, R67)."""

from __future__ import annotations

import pytest

from axon_ai.http.domain.scopes import ACCOUNTS, ADMIN, ANY_KEY, INFERENCE, admin_access, key_reaches

pytestmark = pytest.mark.us13


def test_conjuntos() -> None:
    assert {"inference"} == INFERENCE
    assert {"users", "admin"} == ACCOUNTS
    assert {"admin"} == ADMIN
    assert {"inference", "users", "admin"} == ANY_KEY


@pytest.mark.parametrize(
    ("scopes", "route", "expected"),
    [
        (None, INFERENCE, True),  # OIDC: regido pelo grupo, não pelo escopo
        (None, ADMIN, True),
        (frozenset({"inference"}), INFERENCE, True),
        (frozenset({"users"}), INFERENCE, False),
        (frozenset({"admin"}), INFERENCE, False),  # admin não inclui inference (ADR-057 item 1)
        (frozenset({"users"}), ACCOUNTS, True),
        (frozenset({"inference"}), ACCOUNTS, False),
        (frozenset({"users"}), ANY_KEY, True),
        (frozenset({"inference", "users"}), ADMIN, False),
    ],
)
def test_key_reaches(scopes: frozenset[str] | None, route: frozenset[str], expected: bool) -> None:
    assert key_reaches(scopes, route) is expected


@pytest.mark.parametrize(
    ("scopes", "route", "administers", "expected"),
    [
        (None, ADMIN, True, True),  # console de um admin
        (None, ADMIN, False, False),  # console de quem não administra
        (None, ACCOUNTS, False, False),  # OIDC não tem `users`: só o grupo entra
        (frozenset({"users"}), ACCOUNTS, False, True),  # a chave `users` entra sem o grupo
        (frozenset({"users"}), ADMIN, False, False),
        (frozenset({"admin", "inference"}), ADMIN, True, True),
        (frozenset({"admin", "inference"}), ACCOUNTS, True, True),
        (frozenset({"admin"}), ADMIN, False, False),  # escopo sem o grupo (a 003 diz que não administra)
        (frozenset({"inference"}), ACCOUNTS, False, False),  # o grupo sem o escopo (US13 cen. 9)
        (frozenset({"inference"}), ADMIN, False, False),
    ],
)
def test_admin_access(scopes: frozenset[str] | None, route: frozenset[str], administers: bool, expected: bool) -> None:
    assert admin_access(scopes, route, administers=administers) is expected
