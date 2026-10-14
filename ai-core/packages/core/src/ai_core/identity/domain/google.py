"""Login com Google só para contas cadastradas (FR-008; research R9).

Recebe o que o `id_token` verificado afirma e as contas encontradas pelo `sub` do Google e pelo e-mail. Nunca cria
conta (SC-003): no máximo vincula o `sub` à conta cujo e-mail casou.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_core.identity.domain.digest import same
from ai_core.identity.domain.names import normalize_email
from ai_core.identity.domain.records import AccountRecord, GoogleIdentity

type GoogleRefusalReason = Literal["nonce", "not_verified", "domain", "unknown", "inactive", "other_account"]


@dataclass(frozen=True, slots=True, kw_only=True)
class GoogleAccept:
    account_id: str
    link: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class GoogleRefusal:
    reason: GoogleRefusalReason
    email: str | None = None


def email_of(identity: GoogleIdentity) -> str | None:
    return normalize_email(identity.email) if identity.email else None


def decide_google(
    identity: GoogleIdentity,
    *,
    expected_nonce: str | None,
    hosted_domain: str | None,
    by_sub: AccountRecord | None,
    by_email: AccountRecord | None,
) -> GoogleAccept | GoogleRefusal:
    email = email_of(identity)
    if expected_nonce is None or identity.nonce is None or not same(identity.nonce, expected_nonce):
        return GoogleRefusal(reason="nonce")
    if not identity.email_verified or email is None:
        return GoogleRefusal(reason="not_verified")
    if hosted_domain is not None:
        domain = hosted_domain.lower()
        if (identity.hosted_domain or "").lower() != domain or not email.endswith("@" + domain):
            return GoogleRefusal(reason="domain", email=email)
    if by_sub is not None:
        if not by_sub.account.active:
            return GoogleRefusal(reason="inactive", email=email)
        return GoogleAccept(account_id=by_sub.account.id, link=False)
    if by_email is None:
        return GoogleRefusal(reason="unknown", email=email)
    if by_email.google_sub is not None:
        return GoogleRefusal(reason="other_account", email=email)
    if not by_email.account.active:
        return GoogleRefusal(reason="inactive", email=email)
    return GoogleAccept(account_id=by_email.account.id, link=True)
