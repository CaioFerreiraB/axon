"""Claims dos tokens emitidos e a conferência do token de acesso no `userinfo` (FR-006; research R6).

O token de acesso leva a `audience` do cliente (`axon`, `axon-admin` — ADR-031); o de identidade, o `client_id`.
Como nenhuma audiência pode ser id de cliente (`domain/clients.py`), um não se passa pelo outro.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime, timedelta

from axon_ai.identity.api import Account, AuthMethod
from axon_ai.identity.domain.records import Client


def _epoch(instant: datetime) -> int:
    return int(instant.timestamp())


def access_claims(
    *, issuer: str, client: Client, account: Account, scope: str, now: datetime, ttl: timedelta
) -> dict[str, object]:
    return {
        "iss": issuer,
        "aud": client.audience,
        "sub": account.id,
        "preferred_username": account.username,
        "groups": sorted(account.groups),
        "azp": client.id,
        "scope": scope,
        "iat": _epoch(now),
        "exp": _epoch(now + ttl),
    }


def id_claims(
    *,
    issuer: str,
    client: Client,
    account: Account,
    nonce: str | None,
    auth_time: datetime,
    amr: AuthMethod,
    now: datetime,
    ttl: timedelta,
) -> dict[str, object]:
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": client.id,
        "sub": account.id,
        "preferred_username": account.username,
        "name": account.name,
        "email": account.email,
        # O e-mail é cadastrado por um admin (contracts/oidc.md).
        "email_verified": True,
        "groups": sorted(account.groups),
        "azp": client.id,
        "auth_time": _epoch(auth_time),
        "amr": [amr],
        "iat": _epoch(now),
        "exp": _epoch(now + ttl),
    }
    if nonce is not None:
        claims["nonce"] = nonce
    return claims


def userinfo(account: Account) -> dict[str, object]:
    return {
        "sub": account.id,
        "preferred_username": account.username,
        "name": account.name,
        "email": account.email,
        "email_verified": True,
        "groups": sorted(account.groups),
    }


def access_subject(
    claims: Mapping[str, object],
    *,
    issuer: str,
    audiences: Collection[str],
    now: datetime,
    leeway: timedelta = timedelta(seconds=60),
) -> str | None:
    """O `sub` de um token de acesso deste emissor ainda válido, ou `None`. A assinatura já foi conferida."""
    if claims.get("iss") != issuer or claims.get("aud") not in audiences or "scope" not in claims:
        return None
    expires = claims.get("exp")
    if not isinstance(expires, int | float) or isinstance(expires, bool):
        return None
    if now.timestamp() > expires + leeway.total_seconds():
        return None
    subject = claims.get("sub")
    return subject if isinstance(subject, str) and subject else None


def hinted_subject(claims: Mapping[str, object], *, issuer: str, client_ids: Collection[str]) -> tuple[str, str] | None:
    """(`sub`, `client_id`) de um `id_token_hint` deste emissor; no logout, a expiração é tolerada (oidc.md)."""
    if claims.get("iss") != issuer:
        return None
    audience, subject = claims.get("aud"), claims.get("sub")
    if not isinstance(audience, str) or audience not in client_ids or not isinstance(subject, str):
        return None
    return subject, audience
