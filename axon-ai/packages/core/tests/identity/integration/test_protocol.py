"""T023/T041 — suíte de protocolo com o authlib como RP sobre o app em processo (contracts/oidc.md; SC-002).

Parte 1 (US1): descoberta com backchannel dinâmico, login por usuário e por e-mail, código → tokens por
`client_secret_basic` e `client_secret_post`, token de identidade validado pelo authlib, `userinfo`, código reusado.
Parte 2 (US3): cliente público com PKCE, audiências, renovação com rotação e reuso, revogação e logout.
"""

from __future__ import annotations

import warnings
from datetime import timedelta
from typing import Any

import httpx
import httpx2
import jwt
import pytest
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oidc.core import CodeIDToken
from identity_testkit import (
    CONSOLE,
    CONSOLE_CALLBACK,
    ISSUER,
    OPEN_WEBUI,
    OPEN_WEBUI_CALLBACK,
    OPEN_WEBUI_SECRET,
    Harness,
    app_for,
    browser,
    hidden_fields,
    login_code,
    pkce_pair,
    query,
)

from axon_ai.identity.adapters.http import IdentityHttpSettings

with warnings.catch_warnings():
    # o `authlib.jose` está em transição para o `joserfc`; a validação de `CodeIDToken` ainda mora nele
    warnings.simplefilter("ignore")
    from authlib.jose import JsonWebKey
    from authlib.jose import jwt as authlib_jwt

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _rp(
    app: Any, client_id: str, *, secret: str | None = None, method: str = "client_secret_basic"
) -> AsyncOAuth2Client:
    """O RP, como o Open WebUI ou a console, falando com o app pelo transporte ASGI (o authlib usa `httpx2`)."""
    return AsyncOAuth2Client(
        client_id=client_id,
        client_secret=secret,
        token_endpoint_auth_method=method if secret else "none",
        code_challenge_method=None if secret else "S256",
        transport=httpx2.ASGITransport(app=app),
        base_url=ISSUER,
    )


async def _validated_id_token(http: httpx.AsyncClient, token: str, *, client_id: str, nonce: str) -> dict[str, Any]:
    jwks = JsonWebKey.import_key_set((await http.get("/oauth2/jwks")).json())
    claims = authlib_jwt.decode(
        token,
        jwks,
        claims_cls=CodeIDToken,
        claims_options={"iss": {"essential": True, "value": ISSUER}},
        claims_params={"nonce": nonce, "client_id": client_id},
    )
    claims.validate(leeway=10**9)  # o relógio da suíte é fixo; a validade é conferida pelo `exp` abaixo
    return dict(claims)


async def test_descoberta_com_backchannel_dinamico(started: Harness) -> None:
    app = app_for(started)
    async with browser(app) as navegador:
        public = (await navegador.get("/.well-known/openid-configuration")).json()
    async with browser(app, base_url="http://ai-core:8000") as conteiner:
        internal = (await conteiner.get("/.well-known/openid-configuration")).json()
        forged = (
            await conteiner.get(
                "/.well-known/openid-configuration",
                headers={"x-forwarded-proto": "https", "x-forwarded-host": "atacante.exemplo"},
            )
        ).json()
    assert public["issuer"] == internal["issuer"] == ISSUER
    assert public["authorization_endpoint"] == internal["authorization_endpoint"] == f"{ISSUER}/oauth2/authorize"
    assert public["token_endpoint"] == f"{ISSUER}/oauth2/token"
    assert internal["token_endpoint"] == "http://ai-core:8000/oauth2/token"
    assert internal["jwks_uri"] == "http://ai-core:8000/oauth2/jwks"
    assert internal["userinfo_endpoint"] == "http://ai-core:8000/oauth2/userinfo"
    # `X-Forwarded-*` de quem não é proxy confiável não muda nada
    assert forged["token_endpoint"] == "http://ai-core:8000/oauth2/token"
    assert public["code_challenge_methods_supported"] == ["S256"]
    assert public["response_types_supported"] == ["code"]


async def test_x_forwarded_de_proxy_confiavel(started: Harness) -> None:
    app = app_for(started, IdentityHttpSettings(trusted_proxies=("203.0.113.0/24",)))
    async with browser(app, base_url="http://ai-core:8000") as proxy:
        document = (
            await proxy.get(
                "/.well-known/openid-configuration",
                headers={"x-forwarded-proto": "https", "x-forwarded-host": "agentic.interno"},
            )
        ).json()
    assert document["token_endpoint"] == "https://agentic.interno/oauth2/token"
    assert document["issuer"] == ISSUER


@pytest.mark.parametrize("identifier", ["ana", "Ana@Exemplo.org"])
@pytest.mark.parametrize("method", ["client_secret_basic", "client_secret_post"])
async def test_login_por_senha_e_tokens_do_cliente_confidencial(
    started: Harness, http: httpx.AsyncClient, identifier: str, method: str
) -> None:
    await started.add_account("ana", groups={"equipe", "admin"})
    app = app_for(started)
    rp = _rp(app, OPEN_WEBUI.id, secret=OPEN_WEBUI_SECRET, method=method)
    url, state = rp.create_authorization_url(
        f"{ISSUER}/oauth2/authorize",
        redirect_uri=OPEN_WEBUI_CALLBACK,
        scope="openid profile email groups",
        nonce="nonce-rp",
    )
    page = await http.get(url)
    assert page.status_code == 200
    fields = hidden_fields(page.text)
    response = await http.post(
        "/oauth2/login", data={**fields, "identifier": identifier, "password": "senha-forte-da-ana"}
    )
    assert response.status_code == 303
    callback = query(response.headers["location"])
    assert response.headers["location"].startswith(OPEN_WEBUI_CALLBACK + "?")
    assert callback["state"] == state
    async with rp:
        token = await rp.fetch_token(f"{ISSUER}/oauth2/token", code=callback["code"], redirect_uri=OPEN_WEBUI_CALLBACK)
    assert token["token_type"] == "Bearer" and token["expires_in"] == 600 and token["refresh_token"]
    identity = await _validated_id_token(http, token["id_token"], client_id=OPEN_WEBUI.id, nonce="nonce-rp")
    assert identity["preferred_username"] == "ana" and identity["email"] == "ana@exemplo.org"
    assert identity["amr"] == ["pwd"] and identity["aud"] == OPEN_WEBUI.id
    header = jwt.get_unverified_header(token["access_token"])
    assert header["alg"] == "RS256" and header["kid"] == started.service.jwks()["keys"][0]["kid"]
    access = jwt.decode(token["access_token"], options={"verify_signature": False})
    assert access["aud"] == "axon" and access["iss"] == ISSUER and access["sub"] == "id-ana"
    assert access["groups"] == ["admin", "equipe"] and access["exp"] - access["iat"] == 600
    info = await http.get("/oauth2/userinfo", headers={"authorization": f"Bearer {token['access_token']}"})
    assert info.status_code == 200
    assert info.json() == {
        "sub": "id-ana",
        "preferred_username": "ana",
        "name": "Ana",
        "email": "ana@exemplo.org",
        "email_verified": True,
        "groups": ["admin", "equipe"],
    }
    assert info.headers["cache-control"] == "no-store"


async def test_userinfo_recusa_token_invalido_e_token_de_identidade(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    code = await login_code(http)
    token = await http.post(
        "/oauth2/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": OPEN_WEBUI_CALLBACK},
        auth=(OPEN_WEBUI.id, OPEN_WEBUI_SECRET),
    )
    id_token = token.json()["id_token"]
    for bearer in (id_token, "lixo", ""):
        response = await http.get("/oauth2/userinfo", headers={"authorization": f"Bearer {bearer}"})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'
    started.clock.advance(timedelta(minutes=12))
    expired = await http.get("/oauth2/userinfo", headers={"authorization": f"Bearer {token.json()['access_token']}"})
    assert expired.status_code == 401


async def test_codigo_reusado_e_recusado_e_revoga_a_renovacao(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    code = await login_code(http)
    exchange = {"grant_type": "authorization_code", "code": code, "redirect_uri": OPEN_WEBUI_CALLBACK}
    auth = (OPEN_WEBUI.id, OPEN_WEBUI_SECRET)
    first = await http.post("/oauth2/token", data=exchange, auth=auth)
    assert first.status_code == 200
    second = await http.post("/oauth2/token", data=exchange, auth=auth)
    assert second.status_code == 400 and second.json()["error"] == "invalid_grant"
    refresh = await http.post(
        "/oauth2/token", data={"grant_type": "refresh_token", "refresh_token": first.json()["refresh_token"]}, auth=auth
    )
    assert refresh.status_code == 400 and refresh.json()["error"] == "invalid_grant"


@pytest.mark.parametrize(
    ("change", "error", "status"),
    [
        ({"redirect_uri": "http://localhost:3000/outro"}, "invalid_grant", 400),
        ({"code": "inventado"}, "invalid_grant", 400),
        ({"grant_type": "password"}, "unsupported_grant_type", 400),
        ({"client_secret": "errado"}, "invalid_client", 401),
    ],
)
async def test_troca_de_codigo_recusada(
    started: Harness, http: httpx.AsyncClient, change: dict[str, str], error: str, status: int
) -> None:
    await started.add_account("ana")
    code = await login_code(http)
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": OPEN_WEBUI_CALLBACK,
        "client_id": OPEN_WEBUI.id,
        "client_secret": OPEN_WEBUI_SECRET,
        **change,
    }
    response = await http.post("/oauth2/token", data=form)
    assert response.status_code == status and response.json()["error"] == error
    assert response.headers["cache-control"] == "no-store"


async def test_codigo_vence_em_60_segundos(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    code = await login_code(http)
    started.clock.advance(timedelta(seconds=61))
    response = await http.post(
        "/oauth2/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": OPEN_WEBUI_CALLBACK},
        auth=(OPEN_WEBUI.id, OPEN_WEBUI_SECRET),
    )
    assert response.json()["error"] == "invalid_grant"


async def test_sessao_existente_dispensa_o_formulario(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    await login_code(http)
    again = await http.get("/oauth2/authorize", params=_params(OPEN_WEBUI, state="dois"))
    assert again.status_code == 302 and query(again.headers["location"])["state"] == "dois"
    forced = await http.get("/oauth2/authorize", params=_params(OPEN_WEBUI, prompt="login"))
    assert forced.status_code == 200 and "Entrar" in forced.text
    silent = await http.get("/oauth2/authorize", params=_params(OPEN_WEBUI, prompt="none"))
    assert "code" in query(silent.headers["location"])


def _params(client: Any, **extra: str) -> dict[str, str]:
    from identity_testkit import authorize_params

    return authorize_params(client, **extra)


async def test_redirect_divergente_mostra_erro_sem_redirecionar(http: httpx.AsyncClient) -> None:
    response = await http.get(
        "/oauth2/authorize", params=_params(OPEN_WEBUI, redirect_uri="https://atacante.exemplo/cb")
    )
    assert response.status_code == 400 and "location" not in response.headers
    assert "Este link de login não é válido" in response.text


# --- Parte 2 (US3) ---------------------------------------------------------------------------------------------------


async def _console_tokens(started: Harness, http: httpx.AsyncClient) -> dict[str, Any]:
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
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_console_com_pkce_pelo_authlib_e_audiencia_propria(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana", groups={"admin"})
    app = app_for(started)
    rp = _rp(app, CONSOLE.id)
    verifier = "v" * 64
    url, _ = rp.create_authorization_url(
        f"{ISSUER}/oauth2/authorize",
        redirect_uri=CONSOLE_CALLBACK,
        scope="openid profile email groups",
        nonce="nonce-console",
        code_verifier=verifier,
    )
    page = await http.get(url)
    fields = hidden_fields(page.text)
    response = await http.post("/oauth2/login", data={**fields, "identifier": "ana", "password": "senha-forte-da-ana"})
    code = query(response.headers["location"])["code"]
    async with rp:
        token = await rp.fetch_token(
            f"{ISSUER}/oauth2/token", code=code, redirect_uri=CONSOLE_CALLBACK, code_verifier=verifier
        )
    access = jwt.decode(token["access_token"], options={"verify_signature": False})
    assert access["aud"] == "axon-admin" and access["azp"] == "console"
    await _validated_id_token(http, token["id_token"], client_id=CONSOLE.id, nonce="nonce-console")


async def test_cliente_publico_sem_pkce_e_recusado(http: httpx.AsyncClient) -> None:
    response = await http.get("/oauth2/authorize", params=_params(CONSOLE))
    assert response.status_code == 302
    assert query(response.headers["location"])["error"] == "invalid_request"


async def test_verificador_errado_e_recusado(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    _, challenge = pkce_pair()
    code = await login_code(http, client=CONSOLE, challenge=challenge)
    response = await http.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CONSOLE_CALLBACK,
            "client_id": CONSOLE.id,
            "code_verifier": "x" * 64,
        },
    )
    assert response.json()["error"] == "invalid_grant"


async def test_renovacao_publica_rotaciona_e_reuso_revoga_a_familia(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    first = await _console_tokens(started, http)

    async def renew(refresh: str) -> httpx.Response:
        return await http.post(
            "/oauth2/token", data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": CONSOLE.id}
        )

    second = await renew(first["refresh_token"])
    assert second.status_code == 200
    rotated = second.json()["refresh_token"]
    assert rotated != first["refresh_token"]
    reused = await renew(first["refresh_token"])
    assert reused.status_code == 400 and reused.json()["error"] == "invalid_grant"
    # o reuso revogou a família: nem o token novo vale mais
    assert (await renew(rotated)).json()["error"] == "invalid_grant"


async def test_renovacao_confidencial_nao_rotaciona(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    code = await login_code(http)
    auth = (OPEN_WEBUI.id, OPEN_WEBUI_SECRET)
    tokens = (
        await http.post(
            "/oauth2/token",
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": OPEN_WEBUI_CALLBACK},
            auth=auth,
        )
    ).json()
    for _ in range(2):
        renewed = await http.post(
            "/oauth2/token", data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]}, auth=auth
        )
        assert renewed.status_code == 200 and renewed.json()["refresh_token"] == tokens["refresh_token"]
    other_client = await http.post(
        "/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CONSOLE.id},
    )
    assert other_client.json()["error"] == "invalid_grant"


async def test_sessao_de_30_dias_e_absoluta(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    tokens = await _console_tokens(started, http)
    started.clock.advance(timedelta(days=30))
    response = await http.post(
        "/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CONSOLE.id},
    )
    assert response.json()["error"] == "invalid_grant"


async def test_revogacao_rfc_7009(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    tokens = await _console_tokens(started, http)
    revoked = await http.post("/oauth2/revoke", data={"token": tokens["refresh_token"], "client_id": CONSOLE.id})
    assert revoked.status_code == 200 and revoked.json() == {}
    unknown = await http.post("/oauth2/revoke", data={"token": "qualquer", "client_id": CONSOLE.id})
    assert unknown.status_code == 200
    renewed = await http.post(
        "/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CONSOLE.id},
    )
    assert renewed.json()["error"] == "invalid_grant"


async def test_logout_com_dica_e_endereco_exato(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    tokens = await _console_tokens(started, http)
    response = await http.get(
        "/oauth2/logout",
        params={
            "id_token_hint": tokens["id_token"],
            "post_logout_redirect_uri": "http://localhost:8080/",
            "state": "saida",
        },
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:8080/?state=saida"
    assert "__Host-axon_session" in response.headers["set-cookie"] and "Max-Age=0" in response.headers["set-cookie"]
    renewed = await http.post(
        "/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CONSOLE.id},
    )
    assert renewed.json()["error"] == "invalid_grant"
    page = await http.get("/oauth2/authorize", params=_params(OPEN_WEBUI))
    assert page.status_code == 200 and "Entrar" in page.text


async def test_logout_sem_endereco_valido_mostra_voce_saiu(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    tokens = await _console_tokens(started, http)
    response = await http.get(
        "/oauth2/logout",
        params={"id_token_hint": tokens["id_token"], "post_logout_redirect_uri": "https://atacante.exemplo/"},
    )
    assert response.status_code == 200 and "Você saiu" in response.text
    assert "location" not in response.headers


@pytest.mark.us8
async def test_cliente_errado_no_token_recebe_o_realm_axon(started: Harness, http: httpx.AsyncClient) -> None:
    """US8 cen. 6 (ADR-037): o desafio do `Basic` diz `axon`."""
    await started.add_account("ana")
    code = await login_code(http)
    response = await http.post(
        "/oauth2/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": OPEN_WEBUI_CALLBACK},
        auth=(OPEN_WEBUI.id, "errado"),
    )
    assert response.status_code == 401 and response.headers["www-authenticate"] == 'Basic realm="axon"'
