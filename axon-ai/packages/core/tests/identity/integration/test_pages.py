"""T025 — páginas do provedor: acessibilidade básica, marca da instalação, cabeçalhos e escape (FR-023; R3, R5)."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from identity_testkit import OPEN_WEBUI, Harness, app_for, authorize_params, browser, harness

from axon_ai.identity.adapters.http import IdentityHttpSettings


async def _login_page(http: httpx.AsyncClient) -> httpx.Response:
    return await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))


async def test_pagina_de_login_acessivel_e_neutra(http: httpx.AsyncClient) -> None:
    response = await _login_page(http)
    page = response.text
    assert '<html lang="pt-BR">' in page
    assert '<label for="identifier">Usuário ou e-mail</label>' in page
    assert 'id="identifier" name="identifier" type="text" autocomplete="username"' in page
    assert 'id="password" name="password" type="password" autocomplete="current-password"' in page
    assert "<title>Entrar · Axon</title>" in page and 'class="lockup"' in page
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


async def test_sem_logotipo_e_404_e_o_nome_proprio_tem_a_inicial(started: Harness) -> None:
    async with browser(app_for(started, IdentityHttpSettings(display_name="Instituto Exemplo"))) as http:
        assert (await http.get("/oauth2/assets/logo")).status_code == 404
        page = (await _login_page(http)).text
    assert '<span class="mark" aria-hidden="true">I</span>' in page and "<span>com Axon</span>" in page


async def test_identificador_digitado_volta_escapado(started: Harness, http: httpx.AsyncClient) -> None:
    from identity_testkit import hidden_fields

    fields = hidden_fields((await _login_page(http)).text)
    response = await http.post(
        "/oauth2/login", data={**fields, "identifier": '"><script>x</script>', "password": "x" * 12}
    )
    assert response.status_code == 401
    assert "<script>x" not in response.text and "&quot;&gt;&lt;script&gt;" in response.text


# --- Identidade Axon (US8; FR-023, ADR-038; research R20, R21) -------------------------------------------------------

BRAND_KIT = Path(__file__).resolve().parents[6] / "brand-kit" / "svg"
BRAND_ASSETS = (
    "axon-lockup-light.svg",
    "axon-lockup-dark.svg",
    "axon-symbol.svg",
    "axon-symbol-light.svg",
    "favicon.svg",
)


@pytest.mark.us8
@pytest.mark.parametrize("name", BRAND_ASSETS)
async def test_os_svg_da_marca_sao_servidos_iguais_ao_brand_kit(http: httpx.AsyncClient, name: str) -> None:
    served = await http.get(f"/oauth2/assets/{name}")
    assert served.status_code == 200 and served.headers["content-type"] == "image/svg+xml"
    assert served.headers["content-security-policy"] == "default-src 'none'; style-src 'unsafe-inline'"
    assert served.headers["cache-control"] == "public, max-age=604800"
    assert served.content == (BRAND_KIT / name).read_bytes()


@pytest.mark.us8
async def test_svg_desconhecido_e_404(http: httpx.AsyncClient) -> None:
    assert (await http.get("/oauth2/assets/axon-lockup-mono.svg")).status_code == 404


@pytest.mark.us8
async def test_a_pagina_aponta_o_favicon_e_o_lockup(http: httpx.AsyncClient) -> None:
    page = (await _login_page(http)).text
    assert '<link rel="icon" type="image/svg+xml" href="/oauth2/assets/favicon.svg">' in page
    assert 'src="/oauth2/assets/axon-lockup-light.svg"' in page


async def test_csp_acompanha_clientes_carregados_depois_do_router() -> None:
    """No perfil `persistent`, o router existe antes de o serviço de runtime carregar o `identity.yaml` (quando o pool
    abre). A CSP precisa das origens dos clientes no `form-action`: sem elas, o Chrome bloqueia o retorno do login por
    senha ao cliente (research R27)."""
    parts = harness()
    app = app_for(parts)
    await parts.service.start()
    async with browser(app) as http:
        csp = (await _login_page(http)).headers["content-security-policy"]
    form_action = re.search(r"form-action ([^;]+)", csp)
    assert form_action is not None
    assert form_action.group(1).split() == ["'self'", "http://localhost:3000", "http://localhost:8080"]
