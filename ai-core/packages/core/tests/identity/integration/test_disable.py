"""T057 — desativar alguém corta o acesso (FR-012, FR-015; SC-004)."""

from __future__ import annotations

import httpx
import jwt
from identity_testkit import (
    CONSOLE,
    CONSOLE_CALLBACK,
    OPEN_WEBUI,
    PASSWORD,
    Harness,
    authorize_params,
    hidden_fields,
    login_code,
    pkce_pair,
)

from ai_core.identity.api import AccountPatch


async def _tokens(http: httpx.AsyncClient) -> dict[str, str]:
    verifier, challenge = pkce_pair()
    code = await login_code(http, client=CONSOLE, challenge=challenge)
    response = await http.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CONSOLE_CALLBACK,
            "client_id": CONSOLE.id,
            "code_verifier": verifier,
        },
    )
    return dict(response.json())


async def test_desativacao_revoga_sessao_e_renovacao(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana", groups={"equipe"})
    tokens = await _tokens(http)
    await started.service.disable("ana", actor="user:root")
    renewed = await http.post(
        "/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CONSOLE.id},
    )
    assert renewed.json()["error"] == "invalid_grant"
    info = await http.get("/oauth2/userinfo", headers={"authorization": f"Bearer {tokens['access_token']}"})
    assert info.status_code == 401
    # o cookie antigo não dispensa mais o login
    page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))
    assert page.status_code == 200 and "Entrar" in page.text
    login = await http.post(
        "/oauth2/login", data={**hidden_fields(page.text), "identifier": "ana", "password": PASSWORD}
    )
    assert login.status_code == 401


async def test_reativada_volta_com_os_grupos_atuais(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana", groups={"equipe"})
    await started.service.disable("ana", actor="user:root")
    await started.accounts.add_group("chefia", at=started.clock.now())
    account = await started.service.enable("ana", actor="user:root")
    await started.service.update(
        "ana", AccountPatch(groups=frozenset({"chefia"})), actor="user:root", version=account.version
    )
    tokens = await _tokens(http)
    access = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    assert access["groups"] == ["chefia"]


async def test_mudanca_de_grupo_vale_no_proximo_token(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana", groups={"equipe"})
    tokens = await _tokens(http)
    current = await started.service.account("ana")
    await started.service.update("ana", AccountPatch(groups=frozenset()), actor="user:root", version=current.version)
    renewed = await http.post(
        "/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CONSOLE.id},
    )
    access = jwt.decode(renewed.json()["access_token"], options={"verify_signature": False})
    assert access["groups"] == []
