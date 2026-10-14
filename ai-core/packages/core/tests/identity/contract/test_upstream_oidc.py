"""T047 — conformidade do `UpstreamOidc`: o adapter real contra um provedor OIDC falso local e o simulado de memória.

O falso faz o papel do Google: descoberta, troca de código (conferindo segredo e PKCE) e `id_token` assinado por uma
chave de teste. As duas versões precisam devolver a mesma `GoogleIdentity` e recusar o PKCE errado.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from identity_testkit import GOOGLE, ISSUER, shared_signer

from ai_core.identity.adapters.google import GoogleOidc
from ai_core.identity.adapters.memory import FixedClock, SimulatedUpstreamOidc
from ai_core.identity.domain.pkce import s256
from ai_core.identity.ports import GoogleIdentity, UpstreamError

FAKE = "https://google.test"
CALLBACK = f"{ISSUER}/oauth2/google/callback"
VERIFIER = "w" * 64


@dataclass
class FakeGoogle:
    """O provedor falso e o que ele afirma sobre a pessoa que aprovou."""

    app: FastAPI
    claims: dict[str, Any]
    requests: dict[str, dict[str, str]]
    issuer: str = "https://accounts.google.com"


def fake_google() -> FakeGoogle:
    key = shared_signer().generate_key()
    app = FastAPI()
    fake = FakeGoogle(app=app, claims={}, requests={})

    @app.get("/.well-known/openid-configuration")
    async def discovery() -> dict[str, str]:
        return {
            "issuer": fake.issuer,
            "authorization_endpoint": f"{FAKE}/auth",
            "token_endpoint": f"{FAKE}/token",
            "jwks_uri": f"{FAKE}/jwks",
        }

    @app.get("/jwks")
    async def jwks() -> dict[str, Any]:
        return {"keys": [dict(key.public_jwk)]}

    @app.post("/token")
    async def token(request: Request) -> JSONResponse:
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        approved = fake.requests.get(form.get("code", ""))
        if (
            approved is None
            or form.get("client_secret") != GOOGLE.client_secret
            or form.get("client_id") != GOOGLE.client_id
            or form.get("redirect_uri") != CALLBACK
            or s256(form.get("code_verifier", "")) != approved["code_challenge"]
        ):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        now = int(time.time())
        claims = {
            "iss": fake.issuer,
            "aud": GOOGLE.client_id,
            "iat": now,
            "exp": now + 3600,
            "nonce": approved["nonce"],
            **fake.claims,
        }
        signed = shared_signer().sign(claims, kid=key.kid, private_pem=key.private_pem)
        return JSONResponse({"id_token": signed, "access_token": "x", "token_type": "Bearer"})

    return fake


def _approve(fake: FakeGoogle, url: str) -> str:
    params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    fake.requests["codigo-do-google"] = params
    return "codigo-do-google"


@pytest.fixture
async def real() -> AsyncIterator[tuple[GoogleOidc, FakeGoogle]]:
    fake = fake_google()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fake.app), base_url=FAKE) as http:
        # o falso assina com o relógio de verdade; o adapter confere a validade pelo relógio da porta
        clock = FixedClock(datetime.now(UTC))
        discovery = f"{FAKE}/.well-known/openid-configuration"
        yield GoogleOidc(client=GOOGLE, redirect_uri=CALLBACK, http=http, clock=clock, discovery_url=discovery), fake


async def test_adapter_real_troca_o_codigo_e_verifica_o_id_token(real: tuple[GoogleOidc, FakeGoogle]) -> None:
    google, fake = real
    fake.claims = {"sub": "g-123", "email": "ana@exemplo.org", "email_verified": True, "hd": "exemplo.org"}
    url = await google.authorization_url(state="st", nonce="nn", code_challenge=s256(VERIFIER))
    query = parse_qs(urlsplit(url).query)
    assert url.startswith(f"{FAKE}/auth?") and query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [CALLBACK] and query["scope"] == ["openid email profile"]
    identity = await google.exchange(code=_approve(fake, url), code_verifier=VERIFIER)
    assert identity == GoogleIdentity(
        sub="g-123", email="ana@exemplo.org", email_verified=True, hosted_domain="exemplo.org", nonce="nn"
    )


async def test_adapter_real_recusa_pkce_errado_emissor_errado_e_codigo_desconhecido(
    real: tuple[GoogleOidc, FakeGoogle],
) -> None:
    google, fake = real
    fake.claims = {"sub": "g-123", "email": "ana@exemplo.org", "email_verified": True}
    url = await google.authorization_url(state="st", nonce="nn", code_challenge=s256(VERIFIER))
    code = _approve(fake, url)
    with pytest.raises(UpstreamError):
        await google.exchange(code=code, code_verifier="x" * 64)
    with pytest.raises(UpstreamError):
        await google.exchange(code="inventado", code_verifier=VERIFIER)
    fake.issuer = "https://outro.test"
    with pytest.raises(UpstreamError, match="outro emissor"):
        await google.exchange(code=code, code_verifier=VERIFIER)


async def test_adapter_real_sem_rede_vira_upstream_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as http:
        google = GoogleOidc(client=GOOGLE, redirect_uri=CALLBACK, http=http, clock=FixedClock())
        with pytest.raises(UpstreamError) as caught:
            await google.authorization_url(state="s", nonce="n", code_challenge=s256(VERIFIER))
    assert GOOGLE.client_secret not in str(caught.value)


async def test_simulado_tem_o_mesmo_contrato() -> None:
    simulated = SimulatedUpstreamOidc()
    url = await simulated.authorization_url(state="st", nonce="nn", code_challenge=s256(VERIFIER))
    assert "state=st" in url
    code = simulated.approve("st", sub="g-123", email="ana@exemplo.org", hosted_domain="exemplo.org")
    with pytest.raises(UpstreamError):
        await simulated.exchange(code=code, code_verifier="x" * 64)
    code = simulated.approve("st", sub="g-123", email="ana@exemplo.org", hosted_domain="exemplo.org")
    identity = await simulated.exchange(code=code, code_verifier=VERIFIER)
    assert identity == GoogleIdentity(
        sub="g-123", email="ana@exemplo.org", email_verified=True, hosted_domain="exemplo.org", nonce="nn"
    )
