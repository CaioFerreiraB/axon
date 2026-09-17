"""Portas secundárias da 002 (specs/002-core-pack-runtime/contracts/ports.md): descoberta e configuração."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from ai_core_contracts import JSONValue


def _empty_config() -> Mapping[str, JSONValue]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True, kw_only=True)
class DiscoveredPack:
    """Pack instalado, antes de importar: `load()` importa e devolve a classe apontada pelo entry point."""

    name: str
    distribution: str
    version: str
    load: Callable[[], object]


@dataclass(frozen=True, slots=True, kw_only=True)
class PackSettings:
    """Habilitação e configuração de um pack, vindas do operador. Pack ausente da configuração = não habilitado."""

    enabled: bool = False
    config: Mapping[str, JSONValue] = field(default_factory=_empty_config)

    def __post_init__(self) -> None:
        object.__setattr__(self, "config", MappingProxyType(copy.deepcopy(dict(self.config))))


class PackSource(Protocol):
    def discover(self) -> Sequence[DiscoveredPack]: ...


class PackConfigSource(Protocol):
    def load(self) -> Mapping[str, PackSettings]:
        """Configuração de packs do operador; levanta `PackConfigError` se estiver malformada."""
        ...
