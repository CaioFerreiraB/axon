"""Formatos de contas, grupos e ajustes de login na administração (contracts/admin-api.md; 012). Puro.

A senha temporária só aparece na resposta que a definiu (`issued_json`), nunca numa leitura (FR-002 da 012).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from axon_ai.http.domain.admin_common import AdminInvalid, flag, only, text, texts, version_of
from axon_ai.identity.api import (
    Account,
    AccountDraft,
    AccountPatch,
    Group,
    IssuedPassword,
    LoginSettingsView,
    Page,
)

_STATES = {"active": True, "disabled": False, "all": None}


def account_json(account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "username": account.username,
        "email": account.email,
        "name": account.name,
        "groups": sorted(account.groups),
        "active": account.active,
        "temporary_password": account.temporary_password,
        "has_password": account.has_password,
        "google_linked": account.google_linked,
        "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
        "updated_by": account.updated_by,
        "last_login_at": account.last_login_at.isoformat() if account.last_login_at else None,
        "version": account.version,
    }


def page_json(page: Page[Account]) -> dict[str, Any]:
    return {"data": [account_json(account) for account in page.items], "next_cursor": page.next_cursor}


def issued_json(issued: IssuedPassword) -> dict[str, Any]:
    return {"account": account_json(issued.account), "temporary_password": issued.temporary_password}


def users_params(params: Mapping[str, str]) -> dict[str, Any]:
    only(params, ("query", "state", "limit", "cursor"))
    state = params.get("state", "active")
    if state not in _STATES:
        raise AdminInvalid("state: 'active', 'disabled' ou 'all'", field="state")
    raw_limit = params.get("limit", "50")
    if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= 200:
        raise AdminInvalid("limit: inteiro de 1 a 200", field="limit")
    return {
        "query": params.get("query") or None,
        "active": _STATES[state],
        "limit": int(raw_limit),
        "cursor": params.get("cursor") or None,
    }


def _value_error_field(error: ValueError, fields: tuple[str, ...]) -> str:
    message = str(error).lower()
    for name, hint in (("username", "usuário"), ("email", "e-mail"), ("name", "nome"), ("groups", "grupo")):
        if name in fields and hint in message:
            return name
    return fields[0]


def draft_body(body: Mapping[str, Any]) -> AccountDraft:
    only(body, ("username", "email", "name", "groups", "google_only"))
    fields = ("username", "email", "name", "groups")
    try:
        return AccountDraft(
            username=(text(body, "username") or "").strip().lower(),
            email=(text(body, "email") or "").strip().lower(),
            name=(text(body, "name") or "").strip(),
            groups=frozenset(texts(body, "groups", optional=True) or ()),
            google_only=bool(flag(body, "google_only", optional=True)),
        )
    except ValueError as error:
        if isinstance(error, AdminInvalid):
            raise
        raise AdminInvalid(str(error), field=_value_error_field(error, fields)) from None


def patch_body(body: Mapping[str, Any]) -> tuple[AccountPatch, int]:
    only(body, ("email", "name", "groups", "version"))
    version = version_of(body)
    assert version is not None
    email = text(body, "email", optional=True)
    groups = texts(body, "groups", optional=True)
    try:
        patch = AccountPatch(
            email=email.strip().lower() if email is not None else None,
            name=text(body, "name", optional=True),
            groups=frozenset(groups) if groups is not None else None,
        )
    except ValueError as error:
        raise AdminInvalid(str(error), field=_value_error_field(error, ("email", "name", "groups"))) from None
    return patch, version


def group_json(group: Group) -> dict[str, Any]:
    return {"name": group.name, "members": group.members, "protected": group.protected}


def group_body(body: Mapping[str, Any]) -> str:
    only(body, ("name",))
    return (text(body, "name") or "").strip().lower()


def members_body(body: Mapping[str, Any]) -> frozenset[str]:
    only(body, ("usernames",))
    return frozenset(name.strip().lower() for name in texts(body, "usernames") or ())


def login_json(view: LoginSettingsView) -> dict[str, Any]:
    return {
        "google_enabled": view.google_enabled,
        "google_source": view.google_source,
        "google_configured": view.google_configured,
        "google_redirect_uri": view.google_redirect_uri,
        "google_client_id": view.google_client_id,
        "google_hosted_domain": view.google_hosted_domain,
        "version": view.version,
    }


def login_body(body: Mapping[str, Any]) -> tuple[bool, int]:
    only(body, ("google_enabled", "version"))
    enabled = flag(body, "google_enabled")
    version = version_of(body)
    assert enabled is not None and version is not None
    return enabled, version
