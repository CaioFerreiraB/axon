"""T024/T054 — respostas de login indistinguíveis (FR-003, SC-005), CSRF, pedido vencido, cookie de sessão e bloqueio
por tentativas (FR-013)."""

from __future__ import annotations

import statistics
import time
from datetime import timedelta

import httpx
import pytest
from identity_testkit import (
    ISSUER,
    OPEN_WEBUI,
    PASSWORD,
    Harness,
    app_for,
    authorize_params,
    browser,
    harness,
    hidden_fields,
)

from axon_ai.identity.adapters.http import IdentityHttpSettings
from axon_ai.identity.adapters.passwords import Argon2PasswordHasher


async def _form(http: httpx.AsyncClient) -> dict[str, str]:
    page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))
    assert page.status_code == 200
    return hidden_fields(page.text)


async def _attempt(http: httpx.AsyncClient, fields: dict[str, str], identifier: str, password: str) -> httpx.Response:
    return await http.post("/oauth2/login", data={**fields, "identifier": identifier, "password": password})


def _without(body: str, identifier: str) -> str:
    return body.replace(identifier, "«identificador»")


async def test_inexistente_senha_errada_e_desativada_sao_indistinguiveis(
    started: Harness, http: httpx.AsyncClient
) -> None:
    await started.add_account("carla")
    await started.add_account("davi", active=False)
    fields = await _form(http)
    responses = {
        "zeca": await _attempt(http, fields, "zeca", PASSWORD),
        "carla": await _attempt(http, fields, "carla", "senha-errada-qualquer"),
        "davi": await _attempt(http, fields, "davi", PASSWORD),
    }
    assert {response.status_code for response in responses.values()} == {401}
    # o corpo só difere pelo identificador digitado, que volta ao campo
    bodies = {_without(response.text, identifier) for identifier, response in responses.items()}
    assert len(bodies) == 1
    assert "Não foi possível entrar com esses dados" in bodies.pop()
    assert all("set-cookie" not in response.headers for response in responses.values())


async def test_tempos_na_mesma_ordem_de_grandeza_com_argon2() -> None:
    parts = harness()
    # argon2 de verdade (parâmetros menores, mesma forma): a diferença de tempo seria o vazamento
    parts.service._hasher = parts.hasher = Argon2PasswordHasher(time_cost=2, memory_cost=16 * 1024, parallelism=1)  # type: ignore[assignment]
    await parts.service.start()
    await parts.add_account("ana")
    await parts.add_account("bia", active=False)
    async with browser(app_for(parts)) as http:
        fields = await _form(http)
        cases = {"inexistente": "zeca", "senha errada": "ana", "desativada": "bia"}
        timings: dict[str, list[float]] = {name: [] for name in cases}
        for _ in range(3):  # menos que o limite de bloqueio por usuário e por origem somados
            for name, identifier in cases.items():
                password = "senha-errada-qualquer" if name == "senha errada" else PASSWORD
                start = time.perf_counter()
                response = await _attempt(http, fields, identifier, password)
                timings[name].append(time.perf_counter() - start)
                assert response.status_code == 401
                parts.attempts.reset(["ip:203.0.113.7", f"id:{identifier}"])
    medians = [statistics.median(values) for values in timings.values()]
    assert max(medians) / min(medians) < 3, timings


async def test_formulario_sem_csrf_ou_com_csrf_errado_e_recusado(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    fields = await _form(http)
    for csrf in ("", "errado"):
        response = await _attempt(http, {**fields, "csrf": csrf}, "ana", PASSWORD)
        assert response.status_code == 403 and "location" not in response.headers
        assert "Não foi possível conferir o formulário" in response.text


async def test_formulario_de_outro_site_e_recusado(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    fields = await _form(http)
    response = await http.post(
        "/oauth2/login",
        data={**fields, "identifier": "ana", "password": PASSWORD},
        headers={"origin": "https://atacante.exemplo"},
    )
    assert response.status_code == 403
    ok = await http.post(
        "/oauth2/login", data={**fields, "identifier": "ana", "password": PASSWORD}, headers={"origin": ISSUER}
    )
    assert ok.status_code == 303


async def test_pedido_vencido_nao_redireciona(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    fields = await _form(http)
    started.clock.advance(timedelta(minutes=10))
    response = await _attempt(http, fields, "ana", PASSWORD)
    assert response.status_code == 400 and "location" not in response.headers
    assert "O link de login expirou" in response.text
    assert "Volte ao aplicativo e entre de novo." in response.text


async def test_formulario_que_nao_e_urlencoded(http: httpx.AsyncClient) -> None:
    response = await http.post("/oauth2/login", json={"identifier": "ana"})
    assert response.status_code == 415
    big = await http.post("/oauth2/login", data={"x": "a" * 20_000})
    assert big.status_code == 413


async def test_cookie_de_sessao_seguro(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    fields = await _form(http)
    response = await _attempt(http, fields, "ana", PASSWORD)
    cookie = response.headers["set-cookie"]
    name, _, attributes = cookie.partition(";")
    assert name.startswith("__Host-axon_session=")
    parts = {item.strip().split("=")[0].lower() for item in attributes.split(";")}
    assert {"max-age", "path", "secure", "httponly", "samesite"} <= parts
    assert "domain" not in parts and "expires" not in parts
    assert "Path=/" in cookie and "SameSite=lax" in cookie and f"Max-Age={30 * 24 * 3600}" in cookie


async def test_cookie_sem_secure_em_desenvolvimento(started: Harness) -> None:
    await started.add_account("ana")
    app = app_for(started, IdentityHttpSettings(cookie_secure=False))
    async with browser(app, base_url="http://localhost:8000") as http:
        fields = await _form(http)
        response = await _attempt(http, fields, "ana", PASSWORD)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("axon_session=") and "Secure" not in cookie


# --- Bloqueio por tentativas (US5) -----------------------------------------------------------------------------------


async def test_sexta_tentativa_com_a_senha_certa_e_recusada(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    fields = await _form(http)
    for _ in range(5):
        assert (await _attempt(http, fields, "ana", "senha-errada-qualquer")).status_code == 401
    locked = await _attempt(http, fields, "ana", PASSWORD)
    assert locked.status_code == 401 and "Não foi possível entrar com esses dados" in locked.text
    started.clock.advance(timedelta(minutes=15))
    fields = await _form(http)
    assert (await _attempt(http, fields, "ana", PASSWORD)).status_code == 303


async def test_inexistente_bloqueia_igual(started: Harness, http: httpx.AsyncClient) -> None:
    fields = await _form(http)
    responses = [await _attempt(http, fields, "zeca", PASSWORD) for _ in range(6)]
    assert {response.status_code for response in responses} == {401}
    assert len({response.text for response in responses}) == 1


async def test_bloqueio_por_origem(started: Harness) -> None:
    await started.add_account("ana")
    app = app_for(started)
    async with browser(app, client=("198.51.100.9", 1)) as attacker:
        fields = await _form(attacker)
        for name in ("u1", "u2", "u3", "u4", "u5"):
            await _attempt(attacker, fields, name, "senha-errada-qualquer")
        assert (await _attempt(attacker, fields, "ana", PASSWORD)).status_code == 401
    async with browser(app, client=("198.51.100.10", 1)) as other:
        fields = await _form(other)
        assert (await _attempt(other, fields, "ana", PASSWORD)).status_code == 303


@pytest.mark.parametrize("trusted", [False, True])
async def test_x_forwarded_for_so_de_proxy_confiavel(started: Harness, trusted: bool) -> None:
    await started.add_account("ana")
    settings = IdentityHttpSettings(trusted_proxies=("10.0.0.0/8",) if trusted else ())
    app = app_for(started, settings)
    async with browser(app, client=("10.0.0.2", 1)) as proxy:
        fields = await _form(proxy)
        for name in ("u1", "u2", "u3", "u4", "u5"):
            await proxy.post(
                "/oauth2/login",
                data={**fields, "identifier": name, "password": "x" * 12},
                headers={"x-forwarded-for": "198.51.100.9"},
            )
        # outra pessoa atrás do mesmo proxy
        response = await proxy.post(
            "/oauth2/login",
            data={**fields, "identifier": "ana", "password": PASSWORD},
            headers={"x-forwarded-for": "198.51.100.20"},
        )
    # com proxy confiável, a origem é o IP real e a Ana entra; sem ele, todos parecem o proxy e ficam bloqueados
    assert response.status_code == (303 if trusted else 401)


@pytest.mark.us8
async def test_o_cookie_com_o_nome_antigo_nao_abre_sessao(started: Harness, http: httpx.AsyncClient) -> None:
    """US8 cen. 5 (ADR-037, corte seco): o mesmo token no cookie `aic_session` não é lido."""
    await started.add_account("ana")
    fields = await _form(http)
    response = await _attempt(http, fields, "ana", PASSWORD)
    name, _, rest = response.headers["set-cookie"].partition("=")
    token = rest.split(";", 1)[0]
    assert name == "__Host-axon_session"
    http.cookies.clear()
    antiga = await http.get("/oauth2/account", headers={"Cookie": f"__Host-aic_session={token}"})
    assert "Minha conta" not in antiga.text
    nova = await http.get("/oauth2/account", headers={"Cookie": f"__Host-axon_session={token}"})
    assert "Minha conta" in nova.text
