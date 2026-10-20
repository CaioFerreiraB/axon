"""Acesso: Principal a partir de claims OIDC, tempo do token, ACL e grupo de administração."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from axon_ai.assistants.api import SUBJECT_PATTERN, Principal


@dataclass(frozen=True, slots=True, kw_only=True)
class OidcClaims:
    """Quais claims viram subject e grupos, e a tolerância de relógio na conferência do tempo (research R6)."""

    subject_claim: str = "sub"
    groups_claim: str = "groups"
    leeway: timedelta = timedelta(seconds=60)


@dataclass(frozen=True, slots=True, kw_only=True)
class OidcAudiences:
    """A audiência que cada superfície aceita (ADR-031, research R26): o token do chat não alcança a administração."""

    public: str = "axon"
    admin: str = "axon-admin"

    def of(self, surface: str) -> str | None:
        return {"public": self.public, "admin": self.admin}.get(surface)


def _instant(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def principal_from_claims(claims: Mapping[str, object], *, now: datetime, config: OidcClaims) -> Principal | None:
    """`user:<subject>` com os grupos do token, ou `None` se o tempo ou o subject não servem.

    `exp` é obrigatório; `nbf` e `iat`, se presentes, não podem estar no futuro além da tolerância. É aqui, e não na
    biblioteca de JWT, que o tempo é conferido: com o relógio da porta, expiração é testável sem esperar (R6).
    """
    current = now.timestamp()
    leeway = config.leeway.total_seconds()

    expires = _instant(claims.get("exp"))
    if expires is None or current > expires + leeway:
        return None
    if "nbf" in claims:
        not_before = _instant(claims["nbf"])
        if not_before is None or current + leeway < not_before:
            return None
    if "iat" in claims:
        issued = _instant(claims["iat"])
        if issued is None or issued > current + leeway:
            return None

    subject = claims.get(config.subject_claim)
    if not isinstance(subject, str) or not SUBJECT_PATTERN.fullmatch(f"user:{subject}"):
        return None
    return Principal(subject=f"user:{subject}", scheme="oidc", groups=_groups(claims.get(config.groups_claim)))


def _groups(value: object) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset({value}) if value.strip() else frozenset()
    if isinstance(value, list | tuple):
        return frozenset(item for item in value if isinstance(item, str) and item.strip())
    return frozenset()


def is_admin(principal: Principal, admin_group: str | None) -> bool:
    """Administra quem pertence ao grupo declarado, em qualquer esquema (ADR-031, research R27): cada superfície já
    limita os esquemas que aceita."""
    return admin_group is not None and admin_group in principal.groups


def selector_matches(selector: str, principal: Principal) -> bool:
    """`*` casa todos; `user:…`/`svc:…`, o subject exato; `group:<g>`, quem tem `g` nos grupos."""
    if selector == "*":
        return True
    if selector.startswith("group:"):
        return selector.removeprefix("group:") in principal.groups
    return selector == principal.subject
