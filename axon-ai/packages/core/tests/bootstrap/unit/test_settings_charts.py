"""`AXON_CHARTS_SCRIPT_BASE_URL` (011 FR-030; ADR-052, item 6; research R57)."""

from __future__ import annotations

import pytest

from axon_ai.bootstrap.health import CHARTS_WITHOUT_URL
from axon_ai.bootstrap.settings import ConfigurationError, EnvConfigSource, Settings


def _env(**values: str) -> Settings:
    return EnvConfigSource({f"AXON_{name}": value for name, value in values.items()}).load()


def test_sem_endereco_os_graficos_ficam_so_na_tabela() -> None:
    settings = _env()
    assert settings.charts_script_base_url is None and settings.charts_base_url is None
    assert "AXON_CHARTS_SCRIPT_BASE_URL" in CHARTS_WITHOUT_URL and "AXON_PUBLIC_URL" in CHARTS_WITHOUT_URL


def test_o_endereco_publico_vale_quando_falta_o_proprio() -> None:
    assert _env(PUBLIC_URL="https://axon.exemplo.org").charts_base_url == "https://axon.exemplo.org"


def test_o_proprio_vence_o_publico() -> None:
    settings = _env(PUBLIC_URL="https://axon.exemplo.org", CHARTS_SCRIPT_BASE_URL="https://cdn.exemplo.org/axon")
    assert settings.charts_base_url == "https://cdn.exemplo.org/axon"
    assert _env(CHARTS_SCRIPT_BASE_URL="http://localhost:8000").charts_base_url == "http://localhost:8000"


@pytest.mark.parametrize("value", ["http://axon.exemplo.org", "axon.exemplo.org", "https://x.org/?v=1"])
def test_endereco_invalido_para_o_boot_nomeando_a_variavel(value: str) -> None:
    with pytest.raises(ConfigurationError, match="AXON_CHARTS_SCRIPT_BASE_URL"):
        _env(CHARTS_SCRIPT_BASE_URL=value)
