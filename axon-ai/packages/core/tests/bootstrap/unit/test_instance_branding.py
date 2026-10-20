"""A marca da instalação para o `/admin/v1/me` (008 US10 cen. 6, FR-032; ADR-038; 008 research R53)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axon_ai.bootstrap.settings import Settings
from axon_ai.bootstrap.wiring import _instance

pytestmark = pytest.mark.us10

IDENTITY = object()
"""Basta a presença: com a identidade ligada, a 012 serve o logotipo."""


def test_sem_nome_nem_logotipo_o_lugar_principal_e_o_axon() -> None:
    branding = _instance(Settings(), None)
    assert (branding.name, branding.logo_url, branding.custom) == ("Axon", None, False)


def test_nome_axon_explicito_continua_sem_marca_propria() -> None:
    assert _instance(Settings(display_name="Axon"), None).custom is False


def test_nome_proprio_e_marca_da_instalacao() -> None:
    branding = _instance(Settings(display_name="Instituto Exemplo"), None)
    assert (branding.name, branding.custom) == ("Instituto Exemplo", True)


def test_logotipo_servido_e_marca_da_instalacao(tmp_path: Path) -> None:
    branding = _instance(Settings(logo_file=tmp_path / "logo.svg"), IDENTITY)  # type: ignore[arg-type]
    assert (branding.logo_url, branding.custom) == ("/oauth2/assets/logo", True)


def test_logotipo_sem_identidade_nao_e_servido_nem_conta(tmp_path: Path) -> None:
    branding = _instance(Settings(logo_file=tmp_path / "logo.svg"), None)
    assert (branding.logo_url, branding.custom) == (None, False)
