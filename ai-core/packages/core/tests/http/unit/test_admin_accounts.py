"""T084 — corpos de contas, grupos e login na administração (contracts/admin-api.md; 012)."""

from __future__ import annotations

from typing import Any

import pytest

from ai_core.http.domain.admin_accounts import (
    draft_body,
    group_body,
    login_body,
    members_body,
    patch_body,
    users_params,
)
from ai_core.http.domain.admin_common import AdminInvalid

pytestmark = pytest.mark.us9


def _field(call: Any, body: Any) -> str:
    with pytest.raises(AdminInvalid) as caught:
        call(body)
    return caught.value.field


def test_rascunho_normaliza_e_recusa() -> None:
    draft = draft_body({"username": " Ana ", "email": "Ana@Exemplo.org", "name": "Ana Souza", "groups": ["equipe"]})
    assert (draft.username, draft.email, draft.groups, draft.google_only) == (
        "ana",
        "ana@exemplo.org",
        frozenset({"equipe"}),
        False,
    )
    assert _field(draft_body, {"username": "ana", "email": "ana@x.org", "name": "Ana", "senha": "x"}) == "senha"
    assert _field(draft_body, {"username": "ana", "name": "Ana"}) == "email"
    assert _field(draft_body, {"username": "a b", "email": "ana@x.org", "name": "Ana"}) == "username"
    assert _field(draft_body, {"username": "ana", "email": "sem-arroba", "name": "Ana"}) == "email"


def test_alteracao_exige_versao() -> None:
    patch, version = patch_body({"name": "Ana S.", "version": 2})
    assert patch.name == "Ana S." and patch.email is None and version == 2
    assert _field(patch_body, {"name": "Ana"}) == "version"
    assert _field(patch_body, {"name": "Ana", "version": None}) == "version"
    assert _field(patch_body, {"username": "outra", "version": 1}) == "username"


def test_listagem_grupos_e_login() -> None:
    assert users_params({}) == {"query": None, "active": True, "limit": 50, "cursor": None}
    assert users_params({"state": "all", "limit": "10"})["active"] is None
    assert _field(users_params, {"state": "apagado"}) == "state"
    assert _field(users_params, {"limit": "0"}) == "limit"
    assert group_body({"name": " Equipe "}) == "equipe"
    assert members_body({"usernames": ["Ana", "bia"]}) == frozenset({"ana", "bia"})
    assert _field(members_body, {"usernames": "ana"}) == "usernames"
    assert login_body({"google_enabled": True, "version": 2}) == (True, 2)
    assert _field(login_body, {"google_enabled": "sim", "version": 2}) == "google_enabled"
    assert _field(login_body, {"google_enabled": True}) == "version"
