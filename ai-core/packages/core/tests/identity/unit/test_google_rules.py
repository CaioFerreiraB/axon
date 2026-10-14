"""T045 — decisão do login Google: só contas cadastradas, ativas e com e-mail verificado (FR-008; SC-003)."""

from __future__ import annotations

import pytest
from identity_testkit import account

from ai_core.identity.domain.google import GoogleAccept, GoogleRefusal, decide_google
from ai_core.identity.ports import AccountRecord, GoogleIdentity

ANA = account("ana")
LINKED = account("bia", google_sub="google-bia")


def _identity(**changes: object) -> GoogleIdentity:
    values: dict[str, object] = {
        "sub": "google-ana",
        "email": "Ana@Exemplo.org",
        "email_verified": True,
        "hosted_domain": None,
        "nonce": "n-1",
    }
    values.update(changes)
    return GoogleIdentity(**values)  # type: ignore[arg-type]


def _decide(
    identity: GoogleIdentity,
    *,
    by_sub: AccountRecord | None = None,
    by_email: AccountRecord | None = ANA,
    hosted_domain: str | None = None,
    expected_nonce: str | None = "n-1",
) -> GoogleAccept | GoogleRefusal:
    return decide_google(
        identity, expected_nonce=expected_nonce, hosted_domain=hosted_domain, by_sub=by_sub, by_email=by_email
    )


def test_primeiro_sucesso_vincula_pelo_email() -> None:
    assert _decide(_identity()) == GoogleAccept(account_id="id-ana", link=True)


def test_ja_vinculada_entra_pelo_sub_mesmo_com_outro_email() -> None:
    decision = _decide(_identity(sub="google-bia", email="bia.nova@gmail.com"), by_sub=LINKED, by_email=None)
    assert decision == GoogleAccept(account_id="id-bia", link=False)


@pytest.mark.parametrize(
    ("identity", "kwargs", "reason"),
    [
        (_identity(nonce="outro"), {}, "nonce"),
        (_identity(nonce=None), {}, "nonce"),
        (_identity(), {"expected_nonce": None}, "nonce"),
        (_identity(email_verified=False), {}, "not_verified"),
        (_identity(email=None), {}, "not_verified"),
        (_identity(hosted_domain="outro.org"), {"hosted_domain": "exemplo.org"}, "domain"),
        (_identity(hosted_domain=None), {"hosted_domain": "exemplo.org"}, "domain"),
        (_identity(email="zeca@exemplo.org"), {"by_email": None}, "unknown"),
        (_identity(), {"by_email": account("ana", active=False)}, "inactive"),
        (_identity(sub="google-outro"), {"by_email": account("ana", google_sub="google-ana")}, "other_account"),
        (_identity(sub="google-bia"), {"by_sub": account("bia", google_sub="google-bia", active=False)}, "inactive"),
    ],
)
def test_recusas(identity: GoogleIdentity, kwargs: dict[str, object], reason: str) -> None:
    decision = _decide(identity, **kwargs)  # type: ignore[arg-type]
    assert isinstance(decision, GoogleRefusal) and decision.reason == reason


def test_dominio_aceito_casa_hd_e_sufixo() -> None:
    decision = _decide(_identity(hosted_domain="Exemplo.org"), hosted_domain="exemplo.org")
    assert isinstance(decision, GoogleAccept)


def test_recusa_de_desconhecido_traz_o_email_normalizado() -> None:
    decision = _decide(_identity(email=" Zeca@Gmail.com "), by_email=None)
    assert decision == GoogleRefusal(reason="unknown", email="zeca@gmail.com")
