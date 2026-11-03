"""`AXON_IMPACT_*` (011 FR-031; ADR-056, item 7; research R54)."""

from __future__ import annotations

import pytest

from axon_ai.bootstrap.observability import impact_estimator
from axon_ai.bootstrap.settings import ConfigurationError, EnvConfigSource, Settings
from axon_ai.observability.adapters.ecologits import EcologitsEstimator

pytestmark = pytest.mark.us8


def _env(**values: str) -> Settings:
    return EnvConfigSource({f"AXON_{name}": value for name, value in values.items()}).load()


def test_padroes() -> None:
    settings = _env()
    assert (settings.impact_enabled, settings.impact_zone, settings.impact_tree_kg_co2e) == (True, None, 140.0)
    assert isinstance(impact_estimator(settings, {}), EcologitsEstimator)


def test_desligado_nao_monta_o_estimador() -> None:
    assert impact_estimator(_env(IMPACT_ENABLED="false"), {}) is None


def test_zona_conhecida_e_fator() -> None:
    settings = _env(IMPACT_ZONE="BRA", IMPACT_TREE_KG_CO2E="163.5")
    assert (settings.impact_zone, settings.impact_tree_kg_co2e) == ("BRA", 163.5)


@pytest.mark.parametrize(
    ("values", "variable"),
    [
        ({"IMPACT_ZONE": "XXX"}, "AXON_IMPACT_ZONE"),
        ({"IMPACT_TREE_KG_CO2E": "0"}, "AXON_IMPACT_TREE_KG_CO2E"),
        ({"IMPACT_TREE_KG_CO2E": "muitas"}, "AXON_IMPACT_TREE_KG_CO2E"),
        ({"IMPACT_ENABLED": "talvez"}, "AXON_IMPACT_ENABLED"),
    ],
)
def test_valor_invalido_para_o_boot_nomeando_a_variavel(values: dict[str, str], variable: str) -> None:
    with pytest.raises(ConfigurationError, match=variable):
        _env(**values)


def test_zona_desconhecida_com_a_estimativa_desligada_nao_importa() -> None:
    assert _env(IMPACT_ENABLED="false", IMPACT_ZONE="XXX").impact_zone == "XXX"
