"""T022 — claims dos tokens de acesso e de identidade (FR-006; R6; ADR-031)."""

from __future__ import annotations

from datetime import timedelta

from identity_testkit import CONSOLE, ISSUER, OPEN_WEBUI, T0, account

from axon_ai.identity.domain.tokens import access_claims, access_subject, hinted_subject, id_claims, userinfo

TTL = timedelta(minutes=10)
ANA = account("ana", groups={"equipe", "admin"}).account
EPOCH = int(T0.timestamp())


def test_claims_de_acesso_com_audiencia_do_cliente() -> None:
    claims = access_claims(issuer=ISSUER, client=OPEN_WEBUI, account=ANA, scope="openid", now=T0, ttl=TTL)
    assert claims == {
        "iss": ISSUER,
        "aud": "ai-core",
        "sub": "id-ana",
        "preferred_username": "ana",
        "groups": ["admin", "equipe"],
        "azp": "open-webui",
        "scope": "openid",
        "iat": EPOCH,
        "exp": EPOCH + 600,
    }
    console = access_claims(issuer=ISSUER, client=CONSOLE, account=ANA, scope="openid", now=T0, ttl=TTL)
    assert console["aud"] == "ai-core-admin" and console["azp"] == "console"


def test_claims_de_identidade() -> None:
    claims = id_claims(
        issuer=ISSUER,
        client=OPEN_WEBUI,
        account=ANA,
        nonce="n-1",
        auth_time=T0 - timedelta(minutes=5),
        amr="pwd",
        now=T0,
        ttl=TTL,
    )
    assert claims["aud"] == "open-webui"
    assert claims["nonce"] == "n-1" and claims["auth_time"] == EPOCH - 300 and claims["amr"] == ["pwd"]
    assert claims["email"] == "ana@exemplo.org" and claims["email_verified"] is True and claims["name"] == "Ana"
    assert claims["exp"] == EPOCH + 600
    without_nonce = id_claims(
        issuer=ISSUER, client=OPEN_WEBUI, account=ANA, nonce=None, auth_time=T0, amr="google", now=T0, ttl=TTL
    )
    assert "nonce" not in without_nonce and without_nonce["amr"] == ["google"]


def test_userinfo() -> None:
    assert userinfo(ANA) == {
        "sub": "id-ana",
        "preferred_username": "ana",
        "name": "Ana",
        "email": "ana@exemplo.org",
        "email_verified": True,
        "groups": ["admin", "equipe"],
    }


def test_token_de_acesso_no_userinfo() -> None:
    claims = access_claims(issuer=ISSUER, client=OPEN_WEBUI, account=ANA, scope="openid", now=T0, ttl=TTL)
    audiences = {"ai-core", "ai-core-admin"}
    assert access_subject(claims, issuer=ISSUER, audiences=audiences, now=T0) == "id-ana"
    assert access_subject(claims, issuer=ISSUER, audiences=audiences, now=T0 + TTL + timedelta(seconds=60)) == "id-ana"
    assert access_subject(claims, issuer=ISSUER, audiences=audiences, now=T0 + TTL + timedelta(seconds=61)) is None
    assert access_subject(claims, issuer="https://outro", audiences=audiences, now=T0) is None
    identity = id_claims(
        issuer=ISSUER, client=OPEN_WEBUI, account=ANA, nonce="n", auth_time=T0, amr="pwd", now=T0, ttl=TTL
    )
    # o token de identidade não serve de token de acesso
    assert access_subject(identity, issuer=ISSUER, audiences=audiences, now=T0) is None
    assert access_subject({**claims, "exp": True}, issuer=ISSUER, audiences=audiences, now=T0) is None


def test_dica_do_logout_tolera_expiracao() -> None:
    identity = id_claims(
        issuer=ISSUER, client=OPEN_WEBUI, account=ANA, nonce="n", auth_time=T0, amr="pwd", now=T0, ttl=TTL
    )
    clients = {"open-webui", "console"}
    assert hinted_subject(identity, issuer=ISSUER, client_ids=clients) == ("id-ana", "open-webui")
    assert hinted_subject({**identity, "aud": "ai-core"}, issuer=ISSUER, client_ids=clients) is None
    assert hinted_subject(identity, issuer="https://outro", client_ids=clients) is None
