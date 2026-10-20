"""Uso de um token de renovação (FR-006, FR-015; data-model.md, transições de `RefreshToken`).

Cliente público: troca a cada uso, e o reuso de um token já trocado revoga a família inteira. Cliente confidencial: não
troca — o Open WebUI renova em paralelo, e a rotação ali criaria corridas (research R6).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from axon_ai.identity.api import Account
from axon_ai.identity.domain.records import Client, RefreshToken, Session

type RefreshDecision = Literal["rotate", "keep", "reuse", "invalid"]


def session_alive(session: Session | None, *, now: datetime) -> bool:
    return session is not None and session.revoked_at is None and now < session.expires_at


def decide_refresh(
    token: RefreshToken | None,
    *,
    client: Client,
    session: Session | None,
    account: Account | None,
    now: datetime,
) -> RefreshDecision:
    if token is None or token.client_id != client.id or token.status == "revoked":
        return "invalid"
    if token.status == "rotated":
        return "reuse"
    if not session_alive(session, now=now) or session is None or session.id_hash != token.session_id:
        return "invalid"
    if account is None or not account.active or account.id != token.account_id:
        return "invalid"
    return "rotate" if client.type == "public" else "keep"
