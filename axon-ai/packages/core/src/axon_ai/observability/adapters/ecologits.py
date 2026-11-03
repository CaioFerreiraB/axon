"""`EcologitsEstimator`: o impacto ambiental de uma chamada pelo EcoLogits (ADR-056; research R44, R45).

Único lugar que importa `ecologits` e `rapidfuzz` (import-linter). Usa a função sem wrapper `llm_impacts`, que não sai
para a rede: a base de modelos e os mixes elétricos vêm no pacote. A resolução do nome é a do domínio, com a
similaridade do `rapidfuzz`, guardada por `(provider, model)`. O EcoLogits avisa por `logger.warning_once`; aqui o
logger fica calado e os avisos vão para a estimativa.
"""

from __future__ import annotations

import logging
from typing import Final

import ecologits
from ecologits.model_repository import models
from ecologits.tracers.utils import PROVIDER_CONFIG_MAP, llm_impacts
from rapidfuzz import fuzz

from axon_ai.observability.domain.impact import ImpactIndex, Resolution, build_index, resolve
from axon_ai.observability.domain.usage_records import ImpactEstimate

logging.getLogger("ecologits").setLevel(logging.ERROR)

_TOTALS: Final = (
    ("energy_kwh", "energy"),
    ("gwp_kgco2eq", "gwp"),
    ("adpe_kgsbeq", "adpe"),
    ("pe_mj", "pe"),
    ("wcf_l", "wcf"),
)
_PHASES: Final = (("usage", "usage"), ("embodied", "embodied"))
_PHASED: Final = (("gwp", "gwp"), ("adpe", "adpe"), ("pe", "pe"))


def _range(impact: object) -> tuple[float, float]:
    """`RangeValue(min, max)` ou um número; impacto ausente vale zero."""
    if impact is None:
        return (0.0, 0.0)
    value = getattr(impact, "value", impact)
    if hasattr(value, "min") and hasattr(value, "max"):
        return (float(value.min), float(value.max))
    number = float(value)  # type: ignore[arg-type]
    return (number, number)


def _ratio(left: str, right: str) -> float:
    return float(fuzz.ratio(left, right))


class EcologitsEstimator:
    def __init__(self, *, zone: str | None = None) -> None:
        self._zone = zone
        self._index: ImpactIndex = build_index((m.provider.value, m.name) for m in models.list_models())
        self._resolved: dict[tuple[str, str], Resolution | None] = {}

    @property
    def version(self) -> str:
        return str(ecologits.__version__)

    @staticmethod
    def known_zone(zone: str) -> bool:
        """Se o EcoLogits tem o mix elétrico da zona (ISO alpha-3): a 011 confere `AXON_IMPACT_ZONE` no boot."""
        probe = llm_impacts("openai", "gpt-4.1-mini", 1, 1.0, electricity_mix_zone=zone)
        return not probe.errors

    def estimate(self, provider: str, model: str, output_tokens: int, latency_s: float) -> ImpactEstimate | None:
        key = (provider, model)
        if key not in self._resolved:
            self._resolved[key] = resolve(provider, model, self._index, _ratio)
        found = self._resolved[key]
        if found is None:
            return None
        result = llm_impacts(found.provider, found.name, output_tokens, latency_s, electricity_mix_zone=self._zone)
        if result.errors:
            return None
        values: dict[str, float] = {}
        for name, attribute in _TOTALS:
            values[f"{name}_min"], values[f"{name}_max"] = _range(getattr(result, attribute))
        for name, attribute in _PHASED:
            for phase, group in _PHASES:
                values[f"{name}_{phase}_min"], values[f"{name}_{phase}_max"] = _range(
                    getattr(getattr(result, group), attribute, None)
                )
        zone = self._zone or PROVIDER_CONFIG_MAP[found.provider].datacenter_location
        return ImpactEstimate(
            model=f"{found.provider}/{found.name}",
            match=found.match,
            zone=zone,
            version=self.version,
            values=values,
            warnings=tuple(str(getattr(warning, "code", warning)) for warning in (result.warnings or ())),
        )
