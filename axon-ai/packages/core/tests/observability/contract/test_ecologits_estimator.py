"""T090 — o `EcologitsEstimator` contra o EcoLogits real (009 US9; research R44, R45): determinístico e sem rede."""

from __future__ import annotations

import ecologits
import pytest

from axon_ai.observability.adapters.ecologits import EcologitsEstimator
from axon_ai.observability.domain.usage_records import IMPACT_COLUMNS

pytestmark = pytest.mark.us9


@pytest.fixture(scope="module")
def estimator() -> EcologitsEstimator:
    return EcologitsEstimator()


def test_exato_com_faixa_zona_e_versao(estimator: EcologitsEstimator) -> None:
    found = estimator.estimate("openrouter", "openai/gpt-4.1-mini", 500, 3.0)
    assert found is not None
    assert (found.model, found.match, found.zone) == ("openai/gpt-4.1-mini", "exact", "USA")
    assert found.version == estimator.version == ecologits.__version__
    assert set(found.values) == set(IMPACT_COLUMNS)
    assert 0.00002 < found.values["gwp_kgco2eq_min"] <= found.values["gwp_kgco2eq_max"] < 0.0002
    assert 0 < found.values["energy_kwh_min"] <= found.values["energy_kwh_max"]
    assert found.values["gwp_embodied_max"] > 0
    assert "model-arch-not-released" in found.warnings


def test_aproximado_da_mesma_familia(estimator: EcologitsEstimator) -> None:
    found = estimator.estimate("openrouter", "z-ai/glm-5.3-flash", 500, 4.0)
    assert found is not None
    assert (found.model, found.match) == ("mistralai/zai-glm-5-3", "approximate")


@pytest.mark.parametrize(("provider", "model"), [("ollama", "qwen3:1.7b"), ("openrouter", "deepseek/deepseek-chat")])
def test_sem_par(estimator: EcologitsEstimator, provider: str, model: str) -> None:
    assert estimator.estimate(provider, model, 500, 3.0) is None


def test_zona_da_instalacao() -> None:
    found = EcologitsEstimator(zone="BRA").estimate("openai", "gpt-4.1-mini", 500, 3.0)
    assert found is not None and found.zone == "BRA"
    assert EcologitsEstimator.known_zone("BRA")
    assert not EcologitsEstimator.known_zone("XXX")


def test_resolucao_em_cache(estimator: EcologitsEstimator, monkeypatch: pytest.MonkeyPatch) -> None:
    estimator.estimate("openrouter", "openai/gpt-4.1-nano", 100, 1.0)
    calls: list[str] = []
    import axon_ai.observability.adapters.ecologits as module

    original = module.resolve
    monkeypatch.setattr(module, "resolve", lambda *args: calls.append("x") or original(*args))
    estimator.estimate("openrouter", "openai/gpt-4.1-nano", 200, 2.0)
    assert calls == []
