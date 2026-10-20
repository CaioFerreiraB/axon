"""A marca nas páginas do provedor (US8 cenários 1 a 3; FR-023 reescrita pelo ADR-038; research R20)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from axon_ai.identity.adapters import pages
from axon_ai.identity.api import Account
from axon_ai.identity.domain.outcomes import AccountPage, ErrorPage, LoginForm, PasswordForm

pytestmark = pytest.mark.us8

AT = datetime(2026, 10, 20, tzinfo=UTC)
ACCOUNT = Account(id="id-ana", username="ana", email="ana@exemplo.org", name="Ana", created_at=AT, updated_at=AT)

PAGES: dict[str, Callable[[pages.Brand], str]] = {
    "login": lambda brand: pages.login_page(LoginForm(request="r", csrf="c", google=False), brand),
    "senha": lambda brand: pages.password_page(PasswordForm(request="r", csrf="c"), brand),
    "conta": lambda brand: pages.account_page(AccountPage(account=ACCOUNT, csrf="c"), brand),
    "erro": lambda brand: pages.error_page(ErrorPage(status=400, title="Pedido inválido", message="m"), brand),
    "saida": pages.logged_out_page,
}
LOCKUP = '<img class="lockup" src="/oauth2/assets/axon-lockup-light.svg" alt="Axon"'
DARK_LOCKUP = '<source media="(prefers-color-scheme: dark)" srcset="/oauth2/assets/axon-lockup-dark.svg">'
FAVICON = '<link rel="icon" type="image/svg+xml" href="/oauth2/assets/favicon.svg">'


def test_o_nome_padrao_e_axon() -> None:
    assert pages.DEFAULT_NAME == "Axon" and pages.Brand().name == "Axon" and not pages.Brand().custom


@pytest.mark.parametrize("page", PAGES)
def test_sem_marca_propria_o_lockup_ocupa_o_lugar_principal(page: str) -> None:
    html = PAGES[page](pages.Brand())
    assert LOCKUP in html and DARK_LOCKUP in html
    assert 'class="attribution"' not in html and 'class="brand-name"' not in html
    assert " · Axon</title>" in html


@pytest.mark.parametrize("page", PAGES)
def test_com_marca_propria_ela_fica_no_lugar_principal_e_o_axon_no_rodape(page: str) -> None:
    html = PAGES[page](pages.Brand(name="Instituto Exemplo", custom=True))
    assert 'class="brand-name">Instituto Exemplo<' in html and LOCKUP not in html
    assert '<p class="attribution">' in html and "<span>com Axon</span>" in html
    assert '<img src="/oauth2/assets/axon-symbol-light.svg" alt="" width="16" height="16">' in html
    assert '<source media="(prefers-color-scheme: dark)" srcset="/oauth2/assets/axon-symbol.svg">' in html


def test_logotipo_com_o_nome_padrao_tambem_e_marca_propria() -> None:
    html = PAGES["login"](pages.Brand(has_logo=True, custom=True))
    assert '<img class="mark-image" src="/oauth2/assets/logo"' in html and "<span>com Axon</span>" in html


@pytest.mark.parametrize("brand", [pages.Brand(), pages.Brand(name="Instituto Exemplo", custom=True)])
@pytest.mark.parametrize("page", PAGES)
def test_o_favicon_e_sempre_o_simbolo_axon(page: str, brand: pages.Brand) -> None:
    assert FAVICON in PAGES[page](brand)
