"""T048 — login Google ponta a ponta com o provedor simulado (FR-008, FR-009; SC-002, SC-003)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import jwt
import pytest
from identity_testkit import (
    OPEN_WEBUI,
    OPEN_WEBUI_CALLBACK,
    Harness,
    app_for,
    authorize_params,
    browser,
    harness,
    hidden_fields,
    query,
)

from axon_ai.identity.ports import GoogleClient


@pytest.fixture
async def google_parts() -> Harness:
    parts = harness(google=True)
    await parts.service.start()
    await parts.add_account("ana")
    await parts.add_account("bia", active=False)
    return parts


@pytest.fixture
async def http_google(google_parts: Harness) -> AsyncIterator[httpx.AsyncClient]:
    async with browser(app_for(google_parts)) as client:
        yield client


async def _to_google(parts: Harness, http: httpx.AsyncClient) -> str:
    """Abre o login, clica em "Entrar com Google" e devolve o `state` que foi ao Google."""
    page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))
    assert "Entrar com Google" in page.text
    request = hidden_fields(page.text)["request"]
    start = await http.get("/oauth2/google/start", params={"request": request})
    assert start.status_code == 302 and start.headers["location"].startswith("https://accounts.google.test/")
    return query(start.headers["location"])["state"]


async def _callback(parts: Harness, http: httpx.AsyncClient, state: str, **identity: object) -> httpx.Response:
    code = parts.google.approve(state, **identity)  # type: ignore[arg-type]
    return await http.get("/oauth2/google/callback", params={"state": state, "code": code})


async def test_conta_cadastrada_entra_e_e_vinculada(google_parts: Harness, http_google: httpx.AsyncClient) -> None:
    state = await _to_google(google_parts, http_google)
    response = await _callback(google_parts, http_google, state, sub="google-ana", email="ANA@exemplo.org")
    assert response.status_code == 303 and response.headers["location"].startswith(OPEN_WEBUI_CALLBACK)
    assert "__Host-axon_session" in response.headers["set-cookie"]
    record = await google_parts.accounts.by_username("ana")
    assert record.google_sub == "google-ana" and record.account.google_linked
    tokens = await http_google.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": query(response.headers["location"])["code"],
            "redirect_uri": OPEN_WEBUI_CALLBACK,
        },
        auth=(OPEN_WEBUI.id, "segredo-do-open-webui-de-teste"),
    )
    identity = jwt.decode(tokens.json()["id_token"], options={"verify_signature": False})
    assert identity["amr"] == ["google"] and identity["preferred_username"] == "ana"


@pytest.mark.parametrize(
    ("identity", "message"),
    [
        ({"sub": "google-zeca", "email": "zeca@gmail.com"}, "Conta Google não cadastrada"),
        ({"sub": "google-ana", "email": "ana@exemplo.org", "email_verified": False}, "Não foi possível entrar"),
        ({"sub": "google-bia", "email": "bia@exemplo.org"}, "Não foi possível entrar"),
        ({"sub": "google-ana", "email": "ana@exemplo.org", "nonce": "forjado"}, "Não foi possível entrar"),
    ],
)
async def test_recusas_nunca_criam_conta(
    google_parts: Harness, http_google: httpx.AsyncClient, identity: dict[str, object], message: str
) -> None:
    before = await google_parts.accounts.count()
    state = await _to_google(google_parts, http_google)
    response = await _callback(google_parts, http_google, state, **identity)
    assert response.status_code == 401 and message in response.text
    assert "set-cookie" not in response.headers and "location" not in response.headers
    assert await google_parts.accounts.count() == before  # SC-003
    if identity["email"] == "zeca@gmail.com":
        assert "zeca@gmail.com não tem conta nesta instalação" in response.text
    # a página de recusa traz um formulário novo e válido para tentar com senha
    fields = hidden_fields(response.text)
    retry = await http_google.post(
        "/oauth2/login", data={**fields, "identifier": "ana", "password": "senha-forte-da-ana"}
    )
    assert retry.status_code == 303


async def test_conta_google_diferente_da_vinculada_e_recusada(
    google_parts: Harness, http_google: httpx.AsyncClient
) -> None:
    state = await _to_google(google_parts, http_google)
    await _callback(google_parts, http_google, state, sub="google-ana", email="ana@exemplo.org")
    async with browser(app_for(google_parts)) as other:
        state = await _to_google(google_parts, other)
        response = await _callback(google_parts, other, state, sub="google-intruso", email="ana@exemplo.org")
    assert response.status_code == 401 and "Não foi possível entrar com essa conta Google" in response.text


async def test_state_desconhecido_ou_cancelado(google_parts: Harness, http_google: httpx.AsyncClient) -> None:
    unknown = await http_google.get("/oauth2/google/callback", params={"state": "inventado", "code": "x"})
    assert unknown.status_code == 400 and "O link de login expirou" in unknown.text
    state = await _to_google(google_parts, http_google)
    cancelled = await http_google.get("/oauth2/google/callback", params={"state": state, "error": "access_denied"})
    assert cancelled.status_code == 401 and "Não foi possível entrar com essa conta Google" in cancelled.text


async def test_falha_do_google_vira_recusa(google_parts: Harness, http_google: httpx.AsyncClient) -> None:
    state = await _to_google(google_parts, http_google)
    google_parts.google.fail_exchange = True
    response = await _callback(google_parts, http_google, state, sub="google-ana", email="ana@exemplo.org")
    assert response.status_code == 401


async def test_dominio_aceito_pela_instalacao() -> None:
    parts = harness(google=True)
    parts.secrets._google = GoogleClient(client_id="c", client_secret="s", hosted_domain="exemplo.org")
    await parts.service.start()
    await parts.add_account("ana", email="ana@gmail.com")
    async with browser(app_for(parts)) as http:
        state = await _to_google(parts, http)
        response = await _callback(parts, http, state, sub="g", email="ana@gmail.com", hosted_domain=None)
    assert response.status_code == 401


async def test_botao_e_inicio_so_com_google_ligado_e_configurado(google_parts: Harness) -> None:
    await google_parts.service.set_google(False, actor="user:root", version=0)
    async with browser(app_for(google_parts)) as http:
        page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))
        assert "Entrar com Google" not in page.text
        start = await http.get("/oauth2/google/start", params={"request": hidden_fields(page.text)["request"]})
        assert start.status_code == 404 and "O login com Google não está disponível" in start.text
    unconfigured = harness()
    await unconfigured.service.start()
    async with browser(app_for(unconfigured)) as http:
        page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))
        assert "Entrar com Google" not in page.text
        start = await http.get("/oauth2/google/start", params={"request": hidden_fields(page.text)["request"]})
        assert start.status_code == 404
