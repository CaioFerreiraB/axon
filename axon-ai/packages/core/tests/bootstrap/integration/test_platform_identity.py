"""T054 a T056 (parte da identidade, incremento 9.1) — a plataforma sobe com o provedor de identidade (011 US6; R37 a
R39, R41, R43).

No perfil `test`, a identidade em memória semeia o admin de teste; uma pessoa entra pelo formulário da 012, o token do
cliente do chat vale em `/v1` e o da console não (ADR-031). No `persistent`, contra o Postgres: o admin inicial nasce
uma vez só e as chaves sobrevivem a um restart, carregadas quando o pool de serviço abre.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from bootstrap_testkit import (
    ASSISTANTS_YAML,
    OIDC,
    PUBLIC_URL,
    MemoryConfig,
    bearer,
    chat_token,
    console_token,
    serving,
    write_config,
)

from axon_ai.bootstrap import profiles
from axon_ai.bootstrap.identity import (
    TEST_ADMIN_USERNAME,
    TEST_CHAT_CALLBACK,
    TEST_CHAT_CLIENT,
    TEST_CHAT_SECRET,
)
from axon_ai.bootstrap.profiles import TEST_API_KEY
from axon_ai.bootstrap.wiring import Platform, platform

PG_DSN = os.environ.get("AXON_TEST_POSTGRES_DSN")
needs_pg = pytest.mark.skipif(PG_DSN is None, reason="defina AXON_TEST_POSTGRES_DSN para rodar contra um Postgres")


def _identity_platform(tmp_path: Path, **extra: Any) -> Platform:
    settings = write_config(tmp_path, identity_enabled=True, public_url=PUBLIC_URL, **extra)
    plataforma = platform(config=MemoryConfig(settings))
    assert plataforma.ok, plataforma.report.render()
    return plataforma


async def test_perfil_de_teste_com_identidade_login_e_token_do_chat(tmp_path: Path) -> None:
    plataforma = _identity_platform(tmp_path)
    assert plataforma.identity is not None
    assert [stage.name for stage in plataforma.report.stages][:3] == ["configuration", "adapters", "identity"]
    async with serving(plataforma) as client:
        discovery = (await client.get("/.well-known/openid-configuration")).json()
        assert discovery["issuer"] == PUBLIC_URL
        token = await chat_token(client)
        assert plataforma.access is not None
        principal = await plataforma.access.authenticate(surface="public", credential=token)
        # o subject é o nome de usuário, como na Fase 7 (ACL e donos continuam valendo), e os grupos vêm do token
        assert principal is not None and principal.subject == f"user:{TEST_ADMIN_USERNAME}"
        assert "admin" in principal.groups
        models = await client.get("/v1/models", headers=bearer(token))
        assert models.status_code == 200, models.text
        assert models.json()["data"], "o admin semeado vê os Assistants públicos"
        # o token estático das suítes de pack não vale com a identidade ligada (R39)
        assert (await client.get("/v1/models", headers=OIDC)).status_code == 401
        # a chave de teste continua valendo na superfície privada
        health = await client.get("/private/v1/health", headers=bearer(TEST_API_KEY))
        items = {item["name"]: item for item in health.json()["items"]}
        assert items["identity"]["ok"] is True and items["identity"]["critical"] is True


async def test_token_da_console_nao_vale_no_chat(tmp_path: Path) -> None:
    plataforma = _identity_platform(tmp_path)
    async with serving(plataforma) as client:
        console = await console_token(client)
        assert (await client.get("/v1/models", headers=bearer(console))).status_code == 401


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
    await chat_token(client)
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
        pytest.skip("defina AXON_TEST_POSTGRES_DSN")
    import psycopg

    async with await psycopg.AsyncConnection.connect(PG_DSN, autocommit=True) as connection:
        for schema in ("assistants", "http", "mcp", "capabilities", "identity", "observability"):
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
    monkeypatch.setenv("AXON_BOOTSTRAP_ADMIN_USERNAME", "root")
    monkeypatch.setenv("AXON_BOOTSTRAP_ADMIN_EMAIL", "root@exemplo.org")
    monkeypatch.setenv("AXON_BOOTSTRAP_ADMIN_PASSWORD_FILE", str(password))
    monkeypatch.setenv("AXON_IDENTITY_SECRET_OPEN_WEBUI", TEST_CHAT_SECRET)

    primeira = _persistent_platform(tmp_path, banco_limpo)
    assert primeira.ok, primeira.report.render()
    async with serving(primeira) as client:
        kid = (await client.get("/oauth2/jwks")).json()["keys"][0]["kid"]
        token = await chat_token(client, "root", "senha-do-admin-inicial")
        assert (await client.get("/v1/models", headers=bearer(token))).status_code == 200

    segunda = _persistent_platform(tmp_path, banco_limpo)
    assert segunda.ok, segunda.report.render()
    async with serving(segunda) as client:
        assert (await client.get("/oauth2/jwks")).json()["keys"][0]["kid"] == kid
        # o token emitido pela primeira instância continua valendo na segunda (a chave sobreviveu)
        assert (await client.get("/v1/models", headers=bearer(token))).status_code == 200
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


@needs_pg
async def test_persistent_uso_e_ajustes_dos_destinos_no_banco(
    persistent: None, banco_limpo: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Incremento 9.2: o lote de uso vai ao Postgres pelo ciclo de vida, e os ajustes dos destinos gravados numa
    instância são lidos pela seguinte quando o pool de serviço abre (011 R40, R13)."""
    from axon_ai.observability.api import UsageQuery

    password = tmp_path / "admin.txt"
    password.write_text("senha-do-admin-inicial\n", encoding="utf-8")
    monkeypatch.setenv("AXON_BOOTSTRAP_ADMIN_USERNAME", "root")
    monkeypatch.setenv("AXON_BOOTSTRAP_ADMIN_EMAIL", "root@exemplo.org")
    monkeypatch.setenv("AXON_BOOTSTRAP_ADMIN_PASSWORD_FILE", str(password))
    monkeypatch.setenv("AXON_IDENTITY_SECRET_OPEN_WEBUI", TEST_CHAT_SECRET)
    day = profiles.FIXED_TIME.date()

    primeira = _persistent_platform(tmp_path, banco_limpo)
    assert primeira.ok and primeira.trace is not None and primeira.usage is not None, primeira.report.render()
    assert primeira.destinations is not None
    async with serving(primeira) as client:
        token = await chat_token(client, "root", "senha-do-admin-inicial")
        answer = await client.post(
            "/v1/chat/completions",
            headers=bearer(token),
            json={"model": "geral", "messages": [{"role": "user", "content": "oi"}]},
        )
        assert answer.status_code == 200, answer.text
        await primeira.trace.flush()
        report = await primeira.usage.report(UsageQuery(start=day, end=day))
        assert [(row.key, row.calls) for row in report.totals] == [("ollama/qwen3:1.7b", 1)]
        await primeira.destinations.set_capture(enabled=True, actor="user:root", version=0)

    segunda = _persistent_platform(tmp_path, banco_limpo)
    assert segunda.ok and segunda.usage is not None and segunda.destinations is not None
    async with serving(segunda):
        assert (await segunda.destinations.settings()).capture_content is True
        assert segunda.destinations.capture_enabled()
        report = await segunda.usage.report(UsageQuery(start=day, end=day))
        assert report.totals[0].calls == 1
