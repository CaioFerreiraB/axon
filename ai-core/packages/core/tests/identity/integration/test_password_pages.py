"""T033 — troca obrigatória da senha temporária e "Minha conta" (FR-002, FR-022; contracts/pages.md)."""

from __future__ import annotations

import httpx
from identity_testkit import (
    OPEN_WEBUI,
    OPEN_WEBUI_CALLBACK,
    PASSWORD,
    Harness,
    authorize_params,
    hidden_fields,
    query,
)

NEW = "uma-frase-longa-e-nova"


async def _login(http: httpx.AsyncClient, identifier: str, password: str, *, state: str = "estado-1") -> httpx.Response:
    page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI, state=state))
    return await http.post(
        "/oauth2/login", data={**hidden_fields(page.text), "identifier": identifier, "password": password}
    )


async def test_senha_temporaria_exige_troca_antes_do_codigo(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("bia", password="temporaria-123", temporary=True)
    response = await _login(http, "bia", "temporaria-123")
    assert response.status_code == 200 and "Escolha uma nova senha" in response.text
    assert "location" not in response.headers and "set-cookie" not in response.headers
    fields = hidden_fields(response.text)
    errors = {
        "curta": ("curta", "curta", "pelo menos 12"),
        "confirmação": (NEW, NEW + "x", "A confirmação não é igual"),
        "igual": ("temporaria-123", "temporaria-123", "diferente da temporária"),
    }
    for new, confirm, message in errors.values():
        wrong = await http.post("/oauth2/password", data={**fields, "new_password": new, "confirm": confirm})
        assert wrong.status_code == 400 and message in wrong.text
        assert 'aria-invalid="true"' in wrong.text
    done = await http.post("/oauth2/password", data={**fields, "new_password": NEW, "confirm": NEW})
    assert done.status_code == 303 and done.headers["location"].startswith(OPEN_WEBUI_CALLBACK)
    assert "code" in query(done.headers["location"])
    account = await started.service.account("bia")
    assert not account.temporary_password and account.updated_by == "user:bia"
    # a sessão aberta pela troca dispensa o formulário no pedido seguinte
    again = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI, state="2"))
    assert again.status_code == 302 and "code" in query(again.headers["location"])
    record = await started.accounts.by_username("bia")
    assert await started.hasher.verify(record.password_hash, NEW)


async def test_troca_obrigatoria_nao_aceita_pedido_sem_login(started: Harness, http: httpx.AsyncClient) -> None:
    page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))
    response = await http.post(
        "/oauth2/password", data={**hidden_fields(page.text), "new_password": NEW, "confirm": NEW}
    )
    assert response.status_code == 403


async def test_minha_conta_exige_sessao(http: httpx.AsyncClient) -> None:
    response = await http.get("/oauth2/account")
    assert response.status_code == 200 and "Entrar" in response.text and "Minha conta" not in response.text


async def test_minha_conta_mostra_os_dados_e_troca_a_senha(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana", groups={"equipe"}, name="Ana Souza")
    # outra sessão da Ana, em outro navegador
    other = await started.service.account_login()
    other_login = await started.service.login(
        request=other.request, identifier="ana", password=PASSWORD, csrf=other.csrf, source=None
    )
    assert hasattr(other_login, "session_token")
    await _login(http, "ana", PASSWORD)
    page = await http.get("/oauth2/account")
    assert "Minha conta" in page.text and "Ana Souza" in page.text and "equipe" in page.text
    csrf = hidden_fields(page.text)["csrf"]
    wrong = await http.post(
        "/oauth2/account", data={"csrf": csrf, "current_password": "x" * 12, "new_password": NEW, "confirm": NEW}
    )
    assert wrong.status_code == 400 and "A senha atual não confere." in wrong.text
    forged = await http.post(
        "/oauth2/account", data={"csrf": "x", "current_password": PASSWORD, "new_password": NEW, "confirm": NEW}
    )
    assert forged.status_code == 403
    done = await http.post(
        "/oauth2/account", data={"csrf": csrf, "current_password": PASSWORD, "new_password": NEW, "confirm": NEW}
    )
    assert done.status_code == 200 and "Senha trocada. As suas outras sessões foram encerradas." in done.text
    # a sessão atual continua; a outra caiu
    assert "Minha conta" in (await http.get("/oauth2/account")).text
    other_session = await started.grants.get_session(_digest(other_login.session_token))  # type: ignore[union-attr]
    assert other_session.revoked_at is not None


async def test_senha_atual_errada_conta_para_o_bloqueio(started: Harness, http: httpx.AsyncClient) -> None:
    await started.add_account("ana")
    await _login(http, "ana", PASSWORD)
    csrf = hidden_fields((await http.get("/oauth2/account")).text)["csrf"]
    for _ in range(5):
        await http.post(
            "/oauth2/account", data={"csrf": csrf, "current_password": "x" * 12, "new_password": NEW, "confirm": NEW}
        )
    blocked = await http.post(
        "/oauth2/account", data={"csrf": csrf, "current_password": PASSWORD, "new_password": NEW, "confirm": NEW}
    )
    assert "Muitas tentativas" in blocked.text


async def test_conta_so_google_nao_tem_formulario_de_senha(started: Harness, http: httpx.AsyncClient) -> None:
    from ai_core.identity.api import AccountDraft

    await started.service.create(
        AccountDraft(username="gil", email="gil@exemplo.org", name="Gil", google_only=True), actor="cli"
    )
    form = await started.service.account_login()
    assert form.csrf
    session = await started.service.account_page(None)
    assert hasattr(session, "request")  # sem sessão, o login
    record = await started.accounts.by_username("gil")
    page = await _account_page_for(started, record.account.id)
    assert "Esta conta entra só com o Google" in page and "Trocar senha" not in page


async def _account_page_for(started: Harness, account_id: str) -> str:
    """Abre uma sessão direto no armazenamento (a do Google é testada na US4) e renderiza "Minha conta"."""
    from datetime import timedelta

    from ai_core.identity.adapters.pages import Brand, account_page
    from ai_core.identity.domain.outcomes import AccountPage
    from ai_core.identity.ports import Session

    now = started.clock.now()
    await started.grants.create_session(
        Session(
            id_hash=_digest("token-gil"),
            account_id=account_id,
            auth_time=now,
            amr="google",
            created_at=now,
            expires_at=now + timedelta(days=1),
        )
    )
    outcome = await started.service.account_page("token-gil")
    assert isinstance(outcome, AccountPage) and outcome.csrf is None
    return account_page(outcome, Brand())


def _digest(token: str) -> str:
    from ai_core.identity.domain.digest import digest

    return digest(token)
