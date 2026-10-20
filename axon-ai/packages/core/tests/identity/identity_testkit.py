"""Fábricas da 012: contas, clientes, relógio fixo, Google simulado e o `IdentityService` montado com memória.

Fica num módulo próprio (no `pythonpath` do pytest) para que as suítes o importem sem depender de `conftest`.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import FastAPI

from axon_ai.identity.adapters.cipher import AesGcmCipher
from axon_ai.identity.adapters.http import IdentityHttpSettings, router
from axon_ai.identity.adapters.memory import (
    FastPasswordHasher,
    FixedClock,
    InMemoryAccountStore,
    InMemoryClientSource,
    InMemoryGrantStore,
    InMemoryIdentitySecrets,
    InMemoryIdentitySettingsStore,
    InMemoryLoginAttempts,
    InMemorySigningKeyStore,
    SequentialTokenGenerator,
    SimulatedUpstreamOidc,
)
from axon_ai.identity.adapters.signing import RsaTokenSigner
from axon_ai.identity.api import Account
from axon_ai.identity.ports import AccountRecord, BootstrapAdmin, Client, GoogleClient
from axon_ai.identity.service import IdentityConfig, IdentityService

T0: Final = datetime(2026, 10, 14, 12, tzinfo=UTC)
ISSUER: Final = "https://agentic.exemplo.org"
ADMIN_GROUP: Final = "admin"
MASTER_KEY: Final = bytes(range(32))

OPEN_WEBUI_SECRET: Final = "segredo-do-open-webui-de-teste"
OPEN_WEBUI_CALLBACK: Final = "http://localhost:3000/oauth/oidc/callback"
CONSOLE_CALLBACK: Final = "http://localhost:8080/callback"

OPEN_WEBUI: Final = Client(
    id="open-webui",
    type="confidential",
    audience="axon",
    redirect_uris=(OPEN_WEBUI_CALLBACK,),
    post_logout_redirect_uris=("http://localhost:3000/auth",),
    secret_ref="open_webui",
)
CONSOLE: Final = Client(
    id="console",
    type="public",
    audience="axon-admin",
    redirect_uris=(CONSOLE_CALLBACK,),
    post_logout_redirect_uris=("http://localhost:8080/",),
)
GOOGLE: Final = GoogleClient(client_id="cliente-google.apps.googleusercontent.com", client_secret="segredo-google")

PASSWORD: Final = "senha-forte-da-ana"


def account(
    username: str = "ana",
    *,
    account_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
    groups: frozenset[str] | set[str] = frozenset(),
    active: bool = True,
    temporary: bool = False,
    password_hash: str | None = "fast-v1$x",
    google_sub: str | None = None,
    version: int = 1,
) -> AccountRecord:
    return AccountRecord(
        account=Account(
            id=account_id or f"id-{username}",
            username=username,
            email=email or f"{username}@exemplo.org",
            name=name or username.capitalize(),
            groups=frozenset(groups),
            active=active,
            temporary_password=temporary,
            has_password=password_hash is not None,
            google_linked=google_sub is not None,
            created_at=T0,
            updated_at=T0,
            updated_by="cli",
            version=version,
        ),
        password_hash=password_hash,
        google_sub=google_sub,
    )


_SIGNER: RsaTokenSigner | None = None


def shared_signer() -> RsaTokenSigner:
    """Um assinador por sessão de teste: gerar RSA-2048 a cada caso deixaria a suíte lenta."""
    global _SIGNER
    if _SIGNER is None:
        _SIGNER = RsaTokenSigner()
    return _SIGNER


@dataclass
class Harness:
    """O serviço e as portas em memória, para as suítes mexerem nelas por fora."""

    service: IdentityService
    accounts: Any
    grants: Any
    keys: Any
    settings: Any
    attempts: InMemoryLoginAttempts
    hasher: FastPasswordHasher
    clock: FixedClock
    tokens: SequentialTokenGenerator
    google: SimulatedUpstreamOidc
    secrets: InMemoryIdentitySecrets
    extra: dict[str, Any] = field(default_factory=dict)

    async def add_account(
        self, username: str, *, password: str = PASSWORD, groups: set[str] | frozenset[str] = frozenset(), **kwargs: Any
    ) -> AccountRecord:
        for group in groups:
            if group not in await self.accounts.groups():
                await self.accounts.add_group(group, at=T0)
        record = account(username, groups=frozenset(groups), password_hash=await self.hasher.hash(password), **kwargs)
        await self.accounts.insert(record)
        return record


def harness(
    *,
    google: bool = False,
    google_login: bool | None = None,
    clients: tuple[Client, ...] = (OPEN_WEBUI, CONSOLE),
    client_secrets: dict[str, str] | None = None,
    bootstrap: BootstrapAdmin | None = None,
    public_url: str = ISSUER,
    stores: Any = None,
) -> Harness:
    """Serviço com as portas em memória; `stores` (do conftest) troca os quatro armazenamentos, como o Postgres."""
    clock = FixedClock(T0)
    secrets = InMemoryIdentitySecrets(
        client_secrets={"open_webui": OPEN_WEBUI_SECRET} if client_secrets is None else client_secrets,
        google=GOOGLE if google else None,
        google_login=google_login,
        bootstrap_admin=bootstrap,
    )
    parts = Harness(
        service=None,  # type: ignore[arg-type]
        accounts=stores.accounts if stores else InMemoryAccountStore(),
        grants=stores.grants if stores else InMemoryGrantStore(),
        keys=stores.keys if stores else InMemorySigningKeyStore(),
        settings=stores.settings if stores else InMemoryIdentitySettingsStore(),
        attempts=InMemoryLoginAttempts(),
        hasher=FastPasswordHasher(),
        clock=clock,
        tokens=SequentialTokenGenerator(),
        google=SimulatedUpstreamOidc(),
        secrets=secrets,
    )
    parts.service = IdentityService(
        config=IdentityConfig(public_url=public_url, admin_group=ADMIN_GROUP),
        accounts=parts.accounts,
        grants=parts.grants,
        keys=parts.keys,
        settings=parts.settings,
        attempts=parts.attempts,
        hasher=parts.hasher,
        signer=shared_signer(),
        cipher=AesGcmCipher(MASTER_KEY),
        clients=InMemoryClientSource(clients),
        secrets=secrets,
        clock=clock,
        tokens=parts.tokens,
        google=parts.google if google else None,
    )
    return parts


def app_for(parts: Harness, settings: IdentityHttpSettings | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router(parts.service, settings))
    return app


def browser(
    app: FastAPI, *, base_url: str = ISSUER, client: tuple[str, int] = ("203.0.113.7", 50000)
) -> httpx.AsyncClient:
    """Cliente HTTP em processo (transporte ASGI): guarda o cookie de sessão como um navegador."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=client), base_url=base_url)


# ---------------------------------------------------------------------------------------------------------------------
# Navegador de teste: segue o formulário de login como uma pessoa faria
# ---------------------------------------------------------------------------------------------------------------------

_HIDDEN = re.compile(r'<input type="hidden" name="(?P<name>[a-z_]+)" value="(?P<value>[^"]*)"')


def hidden_fields(html: str) -> dict[str, str]:
    return {match["name"]: match["value"] for match in _HIDDEN.finditer(html)}


def query(location: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(location).query).items()}


def pkce_pair(seed: str = "verificador") -> tuple[str, str]:
    verifier = (seed * 10)[:64]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorize_params(
    client: Client = OPEN_WEBUI,
    *,
    state: str = "estado-1",
    nonce: str = "nonce-1",
    challenge: str | None = None,
    scope: str = "openid profile email groups",
    **extra: str,
) -> dict[str, str]:
    params = {
        "client_id": client.id,
        "redirect_uri": client.redirect_uris[0],
        "response_type": "code",
        "scope": scope,
        "state": state,
        "nonce": nonce,
    }
    if challenge is not None:
        params.update(code_challenge=challenge, code_challenge_method="S256")
    params.update(extra)
    return params


async def login_code(
    http: httpx.AsyncClient,
    *,
    identifier: str = "ana",
    password: str = PASSWORD,
    client: Client = OPEN_WEBUI,
    challenge: str | None = None,
    nonce: str = "nonce-1",
    state: str = "estado-1",
) -> str:
    """Do `authorize` ao código: abre o login, envia o formulário e devolve o `code` do redirecionamento."""
    page = await http.get(
        "/oauth2/authorize", params=authorize_params(client, challenge=challenge, nonce=nonce, state=state)
    )
    assert page.status_code == 200, page.text
    fields = hidden_fields(page.text)
    response = await http.post(
        "/oauth2/login",
        data={**fields, "identifier": identifier, "password": password},
        headers={"origin": ISSUER},
    )
    assert response.status_code == 303, response.text
    params = query(response.headers["location"])
    assert params.get("state") == state
    return params["code"]
