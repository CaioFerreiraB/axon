"""T063 — nenhum segredo nos logs (FR-020) e os eventos de segurança presentes, com usuário e motivo (FR-021; R15)."""

from __future__ import annotations

import logging

import pytest
from identity_testkit import (
    CONSOLE,
    CONSOLE_CALLBACK,
    MASTER_KEY,
    OPEN_WEBUI,
    OPEN_WEBUI_CALLBACK,
    OPEN_WEBUI_SECRET,
    PASSWORD,
    app_for,
    authorize_params,
    browser,
    harness,
    hidden_fields,
    pkce_pair,
    query,
)

from axon_ai.identity.api import AccountDraft, IssuedPassword
from axon_ai.identity.service import LOGGER

NEW = "outra-frase-longa-nova"


async def test_fluxos_completos_nao_vazam_segredos(caplog: pytest.LogCaptureFixture) -> None:
    secrets: list[str] = [PASSWORD, NEW, OPEN_WEBUI_SECRET, "senha-errada-qualquer", "segredo-google"]
    parts = harness(google=True)
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        await parts.service.start()
        await parts.add_account("ana", groups={"equipe"})
        issued = await parts.service.create(AccountDraft(username="bia", email="bia@x.org", name="Bia"), actor="cli")
        assert isinstance(issued, IssuedPassword)
        secrets.append(issued.temporary_password)
        async with browser(app_for(parts)) as http:
            page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI))
            fields = hidden_fields(page.text)
            secrets += [fields["request"], fields["csrf"]]
            await http.post("/oauth2/login", data={**fields, "identifier": "ana", "password": "senha-errada-qualquer"})
            ok = await http.post("/oauth2/login", data={**fields, "identifier": "ana", "password": PASSWORD})
            secrets.append(ok.headers["set-cookie"].split(";")[0].split("=", 1)[1])
            code = query(ok.headers["location"])["code"]
            secrets.append(code)
            exchange = {"grant_type": "authorization_code", "code": code, "redirect_uri": OPEN_WEBUI_CALLBACK}
            tokens = (await http.post("/oauth2/token", data=exchange, auth=(OPEN_WEBUI.id, OPEN_WEBUI_SECRET))).json()
            secrets += [tokens["access_token"], tokens["refresh_token"], tokens["id_token"]]
            await http.post("/oauth2/token", data=exchange, auth=(OPEN_WEBUI.id, OPEN_WEBUI_SECRET))  # reuso
            await http.post("/oauth2/token", data=exchange, auth=(OPEN_WEBUI.id, "segredo-errado-de-cliente"))
            secrets.append("segredo-errado-de-cliente")
            # senha temporária e troca obrigatória
            page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI, prompt="login"))
            temp = await http.post(
                "/oauth2/login",
                data={**hidden_fields(page.text), "identifier": "bia", "password": issued.temporary_password},
            )
            await http.post("/oauth2/password", data={**hidden_fields(temp.text), "new_password": NEW, "confirm": NEW})
            # console com PKCE e renovação rotativa
            verifier, challenge = pkce_pair()
            console = await http.get("/oauth2/authorize", params=authorize_params(CONSOLE, challenge=challenge))
            # a sessão aberta pela troca de senha dispensa o formulário
            console_code = query(console.headers["location"])["code"]
            console_tokens = (
                await http.post(
                    "/oauth2/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": console_code,
                        "redirect_uri": CONSOLE_CALLBACK,
                        "client_id": CONSOLE.id,
                        "code_verifier": verifier,
                    },
                )
            ).json()
            secrets += [console_code, verifier, console_tokens["refresh_token"]]
            await http.post(
                "/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": console_tokens["refresh_token"],
                    "client_id": CONSOLE.id,
                },
            )
            # Google recusado (e-mail sem conta)
            page = await http.get("/oauth2/authorize", params=authorize_params(OPEN_WEBUI, prompt="login"))
            start = await http.get("/oauth2/google/start", params={"request": hidden_fields(page.text)["request"]})
            state = query(start.headers["location"])["state"]
            secrets.append(state)
            google_code = parts.google.approve(state, sub="google-zeca", email="zeca@gmail.com")
            secrets.append(google_code)
            await http.get("/oauth2/google/callback", params={"state": state, "code": google_code})
        reset = await parts.service.reset_password("ana", actor="user:root")
        secrets.append(reset.temporary_password)
        await parts.service.rotate_keys(force=True)
        await parts.service.disable("ana", actor="user:root")

    text = caplog.text + repr([record.__dict__ for record in caplog.records])
    leaked = [secret for secret in secrets if secret and secret in text]
    assert leaked == []
    assert "PRIVATE KEY" not in text and MASTER_KEY.hex() not in text
    events = [getattr(record, "identity", {}).get("event") for record in caplog.records]
    for expected in (
        "login.failed",
        "login.ok",
        "token.code_reused",
        "account.created",
        "account.password_changed",
        "account.password_reset",
        "account.disabled",
        "google.refused",
        "keys.rotated",
    ):
        assert expected in events, expected
    failed = next(record for record in caplog.records if getattr(record, "identity", {}).get("event") == "login.failed")
    assert failed.identity["user"] == "ana" and failed.identity["reason"] == "password"  # type: ignore[attr-defined]
