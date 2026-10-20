"""T040 — uso do token de renovação: rotação para público, reuso, sessão e conta (FR-006, FR-015)."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest
from identity_testkit import CONSOLE, OPEN_WEBUI, T0, account

from axon_ai.identity.domain.refresh import decide_refresh
from axon_ai.identity.ports import RefreshToken, Session

SESSION = Session(
    id_hash="s1", account_id="id-ana", auth_time=T0, amr="pwd", created_at=T0, expires_at=T0 + timedelta(days=30)
)
ANA = account("ana").account


def _token(**changes: object) -> RefreshToken:
    base = RefreshToken(
        hash="r1",
        family_id="f1",
        session_id="s1",
        client_id=CONSOLE.id,
        account_id="id-ana",
        scope="openid",
        created_at=T0,
    )
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


def test_publico_rotaciona_e_confidencial_mantem() -> None:
    assert decide_refresh(_token(), client=CONSOLE, session=SESSION, account=ANA, now=T0) == "rotate"
    confidential = _token(client_id=OPEN_WEBUI.id)
    assert decide_refresh(confidential, client=OPEN_WEBUI, session=SESSION, account=ANA, now=T0) == "keep"


def test_token_ja_rotacionado_e_reuso() -> None:
    rotated = _token(status="rotated", rotated_to="r2")
    assert decide_refresh(rotated, client=CONSOLE, session=SESSION, account=ANA, now=T0) == "reuse"


@pytest.mark.parametrize(
    ("token", "session", "acct", "now"),
    [
        (None, SESSION, ANA, T0),
        (_token(status="revoked"), SESSION, ANA, T0),
        (_token(client_id=OPEN_WEBUI.id), SESSION, ANA, T0),
        (_token(), None, ANA, T0),
        (_token(), dataclasses.replace(SESSION, revoked_at=T0), ANA, T0),
        (_token(), SESSION, ANA, T0 + timedelta(days=30)),
        (_token(), dataclasses.replace(SESSION, id_hash="s2"), ANA, T0),
        (_token(), SESSION, None, T0),
        (_token(), SESSION, dataclasses.replace(ANA, active=False), T0),
    ],
)
def test_invalido(token: RefreshToken | None, session: Session | None, acct: object, now: object) -> None:
    assert decide_refresh(token, client=CONSOLE, session=session, account=acct, now=now) == "invalid"  # type: ignore[arg-type]
