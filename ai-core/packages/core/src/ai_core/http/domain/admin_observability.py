"""Formatos da observabilidade na administração (contracts/admin-api.md; 009 US6, US7). Puro. O segredo do Langfuse
nunca sai: só `secret_set` e a origem de cada campo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ai_core.http.domain.admin_common import AdminInvalid, flag, only, text, version_of
from ai_core.observability.api import ConnectionCheck, DestinationHealth, DestinationSettingsView


def settings_json(view: DestinationSettingsView, health: Sequence[DestinationHealth]) -> dict[str, Any]:
    sources = dict(view.sources)
    return {
        "langfuse": {
            "enabled": view.langfuse_enabled,
            "host": view.langfuse_host,
            "public_key": view.langfuse_public_key,
            "secret_set": view.langfuse_secret_set,
            "sources": {
                "enabled": sources.get("langfuse_enabled", "default"),
                "host": sources.get("langfuse_host", "default"),
                "public_key": sources.get("langfuse_public_key", "default"),
                "secret_key": sources.get("langfuse_secret", "default"),
            },
        },
        "capture_content": view.capture_content,
        "capture_source": sources.get("capture_content", "default"),
        "version": view.version,
        "health": [
            {
                "name": item.name,
                "state": item.state,
                "dropped_24h": item.dropped_24h,
                "last_error": item.last_error,
                "last_sent_at": item.last_sent_at.isoformat() if item.last_sent_at else None,
            }
            for item in health
        ],
    }


def langfuse_body(body: Mapping[str, Any]) -> dict[str, Any]:
    only(body, ("enabled", "host", "public_key", "secret_key", "version"))
    return {
        "enabled": flag(body, "enabled", optional=True),
        "host": text(body, "host", optional=True),
        "public_key": text(body, "public_key", optional=True),
        "secret_key": text(body, "secret_key", optional=True),
        "version": version_of(body),
    }


def capture_body(body: Mapping[str, Any]) -> tuple[bool, int]:
    """Ligar exige `acknowledged: true` — a confirmação do aviso de privacidade (contracts/usage-api.md)."""
    only(body, ("enabled", "acknowledged", "version"))
    enabled = flag(body, "enabled")
    version = version_of(body)
    assert enabled is not None and version is not None
    if enabled and flag(body, "acknowledged", optional=True) is not True:
        raise AdminInvalid(
            "acknowledged: confirme que leu o aviso de privacidade antes de ligar a captura", field="acknowledged"
        )
    return enabled, version


def connection_body(body: Mapping[str, Any]) -> dict[str, Any]:
    only(body, ("host", "public_key", "secret_key"))
    return {
        "host": text(body, "host", optional=True),
        "public_key": text(body, "public_key", optional=True),
        "secret_key": text(body, "secret_key", optional=True),
    }


def check_json(check: ConnectionCheck) -> dict[str, Any]:
    return {"ok": check.ok, "detail": check.detail}
