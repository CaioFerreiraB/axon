"""T054 a T056 (parte da identidade, incremento 9.1) — a plataforma sobe com o provedor de identidade (011 US6; R37 a
R39, R41, R43).

No perfil `test`, a identidade em memória semeia o admin de teste; uma pessoa entra pelo formulário da 012, o token do
cliente do chat vale em `/v1` e o da console não (ADR-031). No `persistent`, contra o Postgres: o admin inicial nasce
uma vez só e as chaves sobrevivem a um restart, carregadas quando o pool de serviço abre.
"""

from __future__ import annotations

import dataclasses
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from bootstrap_testkit import ASSISTANTS_YAML, OIDC, MemoryConfig, write_config

from ai_core.bootstrap import profiles
from ai_core.bootstrap.identity import (
    TEST_ADMIN_PASSWORD,
    TEST_ADMIN_USERNAME,
    TEST_CHAT_CALLBACK,
    TEST_CHAT_CLIENT,
    TEST_CHAT_SECRET,
    TEST_CONSOLE_CALLBACK,
    TEST_CONSOLE_CLIENT,
)
from ai_core.bootstrap.profiles import TEST_API_KEY
from ai_core.bootstrap.wiring import Platform, platform

PUBLIC_URL = "http://localhost:8000"
PG_DSN = os.environ.get("AI_CORE_TEST_POSTGRES_DSN")
needs_pg = pytest.mark.skipif(PG_DSN is None, reason="defina AI_CORE_TEST_POSTGRES_DSN para rodar contra um Postgres")
VERIFIER = "v" * 64
CHALLENGE = "w1TpKUdYE9hUAcNSeeSRFioHDxfUxuHho_JHAfZ_vDM"  # S256 de VERIFIER


def _identity_platform(tmp_path: Path, **extra: Any) -> Platform:
    settings = write_config(tmp_path, identity_enabled=True, public_url=PUBLIC_URL, **extra)
    plataforma = platform(config=MemoryConfig(settings))
    assert plataforma.ok, plataforma.report.render()
    return plataforma


@asynccontextmanager
async def serving(plataforma: Platform) -> AsyncIterator[httpx.AsyncClient]:
    app = plataforma.app
    assert app is not None, plataforma.report.render()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=PUBLIC_URL) as client:
            yield client


def _hidden(html: str) -> dict[str, str]:
    return dict(re.findall(r'<input type="hidden" name="([a-z_]+)" value="([^"]*)"', html))


async def _login(
    client: httpx.AsyncClient, *, client_id: str, callback: str, username: str, password: str, pkce: bool = False
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": callback,
        "response_type": "code",
        "scope": "openid profile email groups",
        "state": "s",
        "nonce": "n",
    }
    if pkce:
        params.update(code_challenge=CHALLENGE, code_challenge_method="S256")
    page = await client.get("/oauth2/authorize", params=params)
    if page.status_code == 302:  # sessão já aberta
        return parse_qs(urlsplit(page.headers["location"]).query)["code"][0]
    assert page.status_code == 200, page.text
    response = await client.post(
        "/oauth2/login", data={**_hidden(page.text), "identifier": username, "password": password}
    )
    assert response.status_code == 303, response.text
    return parse_qs(urlsplit(response.headers["location"]).query)["code"][0]


async def _chat_token(
    client: httpx.AsyncClient, username: str = TEST_ADMIN_USERNAME, password: str = TEST_ADMIN_PASSWORD
) -> str:
    code = await _login(
        client, client_id=TEST_CHAT_CLIENT, callback=TEST_CHAT_CALLBACK, username=username, password=password
    )
    response = await client.post(
        "/oauth2/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": TEST_CHAT_CALLBACK},
        auth=(TEST_CHAT_CLIENT, TEST_CHAT_SECRET),
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


async def _console_token(client: httpx.AsyncClient) -> str:
    code = await _login(
        client,
        client_id=TEST_CONSOLE_CLIENT,
        callback=TEST_CONSOLE_CALLBACK,
        username=TEST_ADMIN_USERNAME,
        password=TEST_ADMIN_PASSWORD,
        pkce=True,
    )
    response = await client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_CONSOLE_CALLBACK,
            "client_id": TEST_CONSOLE_CLIENT,
            "code_verifier": VERIFIER,
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_perfil_de_teste_com_identidade_login_e_token_do_chat(tmp_path: Path) -> None:
    plataforma = _identity_platform(tmp_path)
    assert plataforma.identity is not None
    assert [stage.name for stage in plataforma.report.stages][:3] == ["configuration", "adapters", "identity"]
    async with serving(plataforma) as client:
        discovery = (await client.get("/.well-known/openid-configuration")).json()
        assert discovery["issuer"] == PUBLIC_URL
        token = await _chat_token(client)
        models = await client.get("/v1/models", headers=_bearer(token))
        assert models.status_code == 200, models.text
        assert models.json()["data"], "o admin semeado vê os Assistants públicos"
        # o token estático das suítes de pack não vale com a identidade ligada (R39)
        assert (await client.get("/v1/models", headers=OIDC)).status_code == 401
        # a chave de teste continua valendo na superfície privada
        health = await client.get("/private/v1/health", headers=_bearer(TEST_API_KEY))
        items = {item["name"]: item for item in health.json()["items"]}
        assert items["identity"]["ok"] is True and items["identity"]["critical"] is True


async def test_token_da_console_nao_vale_no_chat(tmp_path: Path) -> None:
    plataforma = _identity_platform(tmp_path)
    async with serving(plataforma) as client:
        console = await _console_token(client)
        assert (await client.get("/v1/models", headers=_bearer(console))).status_code == 401


async def test_sem_identidade_o_token_de_teste_continua_valendo(tmp_path: Path) -> None:
    plataforma = platform(config=MemoryConfig(write_config(tmp_path)))
    assert plataforma.ok and plataforma.identity is None
    async with serving(plataforma) as client:
        assert (await client.get("/v1/models", headers=OIDC)).status_code == 200
        assert (await client.get("/oauth2/jwks")).status_code == 404


async def test_marca_e_logotipo_da_instalacao_nas_paginas(tmp_path: Path) -> None:
    logo = tmp_path / "logo.svg"
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    plataforma = _identity_platform(tmp_path, display_name="Tropa Azul", logo_file=logo)
    async with serving(plataforma) as client:
        page = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": TEST_CHAT_CLIENT,
                "redirect_uri": TEST_CHAT_CALLBACK,
                "response_type": "code",
                "scope": "openid",
                "nonce": "n",
            },
        )
        assert "Tropa Azul" in page.text and "/oauth2/assets/logo" in page.text
        assert (await client.get("/oauth2/assets/logo")).headers["content-type"] == "image/svg+xml"
        assert "aic_session" in (await _login_cookie(client))


async def _login_cookie(client: httpx.AsyncClient) -> str:
    await _chat_token(client)
    return "; ".join(client.cookies.keys())


# --- persistent (Postgres) -------------------------------------------------------------------------------------------


@pytest.fixture
def persistent(monkeypatch: pytest.MonkeyPatch) -> None:
    real = profiles._persistent_profile()
    test = profiles._test_profile()
    factories = dict(real.factories)
    for port in ("clock", "providers"):
        factories[port] = test.factories[port]
    monkeypatch.setitem(profiles.PROFILES, "persistent", lambda: dataclasses.replace(real, factories=factories))  # type: ignore[index]


@pytest.fixture
async def banco_limpo() -> AsyncIterator[str]:
    if PG_DSN is None:
        pytest.skip("defina AI_CORE_TEST_POSTGRES_DSN")
    import psycopg

    async with await psycopg.AsyncConnection.connect(PG_DSN, autocommit=True) as connection:
        for schema in ("assistants", "http", "mcp", "capabilities", "identity"):
            await connection.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    yield PG_DSN


def _persistent_platform(tmp_path: Path, dsn: str, *, master_key: bytes = bytes(range(32))) -> Platform:
    clients = tmp_path / "identity.yaml"
    clients.write_text(
        f"""
version: 1
clients:
  {TEST_CHAT_CLIENT}:
    type: confidential
    secret: open_webui
    audience: ai-core
    redirect_uris: [{TEST_CHAT_CALLBACK}]
""",
        encoding="utf-8",
    )
    settings = dataclasses.replace(
        write_config(tmp_path, assistants=ASSISTANTS_YAML),
        profile="persistent",
        database_url=dsn,
        identity_enabled=True,
        public_url=PUBLIC_URL,
        identity_clients_file=clients,
        master_key=master_key,
    )
    return platform(config=MemoryConfig(settings))


@needs_pg
async def test_persistent_admin_inicial_uma_vez_e_chaves_que_sobrevivem(
    persistent: None, banco_limpo: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    password = tmp_path / "admin.txt"
    password.write_text("senha-do-admin-inicial\n", encoding="utf-8")
    monkeypatch.setenv("AI_CORE_BOOTSTRAP_ADMIN_USERNAME", "root")
    monkeypatch.setenv("AI_CORE_BOOTSTRAP_ADMIN_EMAIL", "root@exemplo.org")
    monkeypatch.setenv("AI_CORE_BOOTSTRAP_ADMIN_PASSWORD_FILE", str(password))
    monkeypatch.setenv("AI_CORE_IDENTITY_SECRET_OPEN_WEBUI", TEST_CHAT_SECRET)

    primeira = _persistent_platform(tmp_path, banco_limpo)
    assert primeira.ok, primeira.report.render()
    async with serving(primeira) as client:
        kid = (await client.get("/oauth2/jwks")).json()["keys"][0]["kid"]
        token = await _chat_token(client, "root", "senha-do-admin-inicial")
        assert (await client.get("/v1/models", headers=_bearer(token))).status_code == 200

    segunda = _persistent_platform(tmp_path, banco_limpo)
    assert segunda.ok, segunda.report.render()
    async with serving(segunda) as client:
        assert (await client.get("/oauth2/jwks")).json()["keys"][0]["kid"] == kid
        # o token emitido pela primeira instância continua valendo na segunda (a chave sobreviveu)
        assert (await client.get("/v1/models", headers=_bearer(token))).status_code == 200
        assert segunda.identity is not None
        page = await segunda.identity.accounts(active=None)
        assert [account.username for account in page.items] == ["root"]


@needs_pg
async def test_persistent_chave_mestra_errada_para_o_boot(persistent: None, banco_limpo: str, tmp_path: Path) -> None:
    assert _persistent_platform(tmp_path, banco_limpo).ok
    plataforma = _persistent_platform(tmp_path, banco_limpo, master_key=bytes(32))
    assert not plataforma.ok
    failure = plataforma.report.failure()
    assert failure is not None and failure.name == "identity"
    assert "keys rotate --force" in (failure.detail or "")
