"""Ajustes dos destinos do trace: precedência instalação > runtime > padrão, com a origem de cada campo (ADR-033,
research R33). Puro: o segredo chega já aberto (ou ausente) — selar e abrir é da porta `SecretCipher`.

Sem console, as chaves do Langfuse ficam na instalação (`AI_CORE_LANGFUSE_*`, tudo ou nada); com ela, na tela, cifradas
no banco. Variável definida vence e aparece somente leitura: o core não precisa saber se há console.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Final
from urllib.parse import urlsplit

from ai_core.observability.api import DestinationSettingsView, InvalidField, SettingSource

LANGFUSE_FIELDS: Final = ("langfuse_enabled", "langfuse_host", "langfuse_public_key", "langfuse_secret")
_LOCAL_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True, slots=True, kw_only=True)
class LangfuseCredentials:
    host: str
    public_key: str
    secret_key: str

    def __repr__(self) -> str:
        return f"LangfuseCredentials(host={self.host!r}, public_key={self.public_key!r}, secret_key='«redigido»')"


@dataclass(frozen=True, slots=True, kw_only=True)
class DestinationSettings:
    """Os ajustes de runtime gravados (ADR-033): o segredo só selado. `None` = não definido (vale o padrão)."""

    langfuse_enabled: bool | None = None
    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_sealed: bytes | None = None
    capture_content: bool | None = None
    version: int = 0
    updated_by: str | None = None
    updated_at: datetime | None = None

    def __repr__(self) -> str:
        return f"DestinationSettings(version={self.version}, langfuse_secret_sealed='«selado»')"


@dataclass(frozen=True, slots=True, kw_only=True)
class InstallationDestinations:
    """O que a instalação define por variável (a 011 lê e valida o grupo do Langfuse, tudo ou nada)."""

    langfuse: LangfuseCredentials | None = None
    capture: bool | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EffectiveDestinations:
    """O que vale agora: as credenciais do Langfuse só quando ligado e completo; e a captura."""

    view: DestinationSettingsView
    langfuse: LangfuseCredentials | None
    capture: bool
    sources: dict[str, SettingSource] = field(default_factory=dict)


def check_host(host: str) -> str:
    """`https`, exceto `localhost` ou nome sem ponto (rede interna do compose)."""
    parts = urlsplit(host.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment:
        raise InvalidField("host: precisa ser uma URL http(s) absoluta", field="host")
    if parts.scheme == "http" and parts.hostname not in _LOCAL_HOSTS and "." in parts.hostname:
        raise InvalidField("host: precisa ser https (http só para localhost ou nome interno)", field="host")
    return host.strip().rstrip("/")


def effective(
    installation: InstallationDestinations, stored: DestinationSettings, *, secret: str | None
) -> EffectiveDestinations:
    """`secret` = o segredo gravado, já aberto (ou `None`)."""
    sources: dict[str, SettingSource] = {}
    credentials: LangfuseCredentials | None = None
    host: str | None
    public_key: str | None
    if installation.langfuse is not None:
        credentials = installation.langfuse
        enabled, host, public_key, secret_set = True, credentials.host, credentials.public_key, True
        sources.update(dict.fromkeys(LANGFUSE_FIELDS, "installation"))
    else:
        enabled = bool(stored.langfuse_enabled)
        host, public_key, secret_set = stored.langfuse_host, stored.langfuse_public_key, secret is not None
        sources["langfuse_enabled"] = "runtime" if stored.langfuse_enabled is not None else "default"
        sources["langfuse_host"] = "runtime" if host is not None else "default"
        sources["langfuse_public_key"] = "runtime" if public_key is not None else "default"
        sources["langfuse_secret"] = "runtime" if secret_set else "default"
        if enabled and host is not None and public_key is not None and secret is not None:
            credentials = LangfuseCredentials(host=host, public_key=public_key, secret_key=secret)
    if installation.capture is not None:
        capture, sources["capture_content"] = installation.capture, "installation"
    else:
        capture = bool(stored.capture_content)
        sources["capture_content"] = "runtime" if stored.capture_content is not None else "default"
    view = DestinationSettingsView(
        langfuse_enabled=enabled,
        langfuse_host=host,
        langfuse_public_key=public_key,
        langfuse_secret_set=secret_set,
        capture_content=capture,
        sources=dict(sources),
        version=stored.version,
    )
    return EffectiveDestinations(view=view, langfuse=credentials, capture=capture, sources=sources)
