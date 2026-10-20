"""Precedência dos ajustes de login: instalação > runtime > padrão, com a origem de cada valor (FR-009, ADR-033)."""

from __future__ import annotations

from axon_ai.identity.api import SettingSource


def google_login(*, installation: bool | None, runtime: bool | None, configured: bool) -> tuple[bool, SettingSource]:
    """Login Google efetivo e de onde ele vem. Sem cliente Google na instalação, nunca está ligado."""
    if installation is not None:
        return installation and configured, "installation"
    if runtime is not None:
        return runtime and configured, "runtime"
    return configured, "default"
