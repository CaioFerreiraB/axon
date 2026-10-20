"""T025 — páginas do provedor: acessibilidade básica, marca da instalação, cabeçalhos e escape (FR-023; R3, R5)."""

from __future__ import annotations

import re

import httpx
from identity_testkit import OPEN_WEBUI, Harness, app_for, authorize_params, browser

from ai_core.identity.adapters.http import IdentityHttpSettings


async def _login_page(http: httpx.AsyncClient) -> httpx.Response:
    return await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))


async def test_pagina_de_login_acessivel_e_neutra(http: httpx.AsyncClient) -> None:
    response = await _login_page(http)
    page = response.text
    assert '<html lang="pt-BR">' in page
    assert '<label for="identifier">Usuário ou e-mail</label>' in page
    assert 'id="identifier" name="identifier" type="text" autocomplete="username"' in page
    assert 'id="password" name="password" type="password" autocomplete="current-password"' in page
    assert "<title>Entrar · Agentic</title>" in page and 'class="brand-name">Agentic<' in page
    assert "Esqueceu a senha? Peça a um administrador para redefinir." in page
    assert "<script" not in page and "style=" not in page
    assert "Entrar com Google" not in page


async def test_cabecalhos_de_seguranca(http: httpx.AsyncClient) -> None:
    response = await _login_page(http)
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "style-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "font-src 'self'" in csp
    form_action = re.search(r"form-action ([^;]+)", csp)
    assert form_action is not None
    assert form_action.group(1).split() == ["'self'", "http://localhost:3000", "http://localhost:8080"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-store"


async def test_fonte_do_desenho_servida_pela_propria_pagina(http: httpx.AsyncClient) -> None:
    """Mona Sans (OFL) nos quatro pesos, sem terceiros — a CSP só aceita fonte da própria origem (R18)."""
    css_href = re.search(r'href="(/oauth2/assets/identity\.[0-9a-f]{12}\.css)"', (await _login_page(http)).text)
    assert css_href is not None
    css = (await http.get(css_href.group(1))).text
    for weight in (400, 500, 600, 700):
        assert f'url("mona-sans-{weight}.woff2")' in css
        font = await http.get(f"/oauth2/assets/mona-sans-{weight}.woff2")
        assert font.status_code == 200 and font.headers["content-type"] == "font/woff2"
        assert font.content[:4] == b"wOF2"
    assert (await http.get("/oauth2/assets/OFL.txt")).status_code == 404


async def test_css_com_hash_e_cache_longo(http: httpx.AsyncClient) -> None:
    page = (await _login_page(http)).text
    href = re.search(r'href="(/oauth2/assets/identity\.[0-9a-f]{12}\.css)"', page)
    assert href is not None
    css = await http.get(href.group(1))
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")
    assert css.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "prefers-color-scheme: dark" in css.text
    assert (await http.get("/oauth2/assets/identity.css")).status_code == 404


async def test_nome_e_logotipo_da_instalacao_com_escape(started: Harness) -> None:
    logo = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    settings = IdentityHttpSettings(display_name="Tropa <Azul> & Cia", logo=(logo, "image/svg+xml"))
    async with browser(app_for(started, settings)) as http:
        page = (await _login_page(http)).text
        served = await http.get("/oauth2/assets/logo")
    assert "Tropa &lt;Azul&gt; &amp; Cia" in page and "<Azul>" not in page
    assert '<img class="mark-image" src="/oauth2/assets/logo"' in page
    assert served.status_code == 200 and served.content == logo
    assert served.headers["content-type"] == "image/svg+xml"
    assert served.headers["content-security-policy"] == "default-src 'none'; style-src 'unsafe-inline'"
    assert served.headers["cache-control"] == "public, max-age=3600"


async def test_sem_logotipo_e_404_e_a_marca_e_a_inicial(http: httpx.AsyncClient) -> None:
    assert (await http.get("/oauth2/assets/logo")).status_code == 404
    page = (await _login_page(http)).text
    assert '<span class="mark" aria-hidden="true">A</span>' in page


async def test_identificador_digitado_volta_escapado(started: Harness, http: httpx.AsyncClient) -> None:
    from identity_testkit import hidden_fields

    fields = hidden_fields((await _login_page(http)).text)
    response = await http.post(
        "/oauth2/login", data={**fields, "identifier": '"><script>x</script>', "password": "x" * 12}
    )
    assert response.status_code == 401
    assert "<script>x" not in response.text and "&quot;&gt;&lt;script&gt;" in response.text
