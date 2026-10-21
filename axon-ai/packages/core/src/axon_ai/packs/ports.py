"""Portas secundárias da 002 (specs/002-core-pack-runtime/contracts/ports.md): descoberta, configuração e diretórios de
dados."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from axon_ai_contracts import JSONValue


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


class PackDataDirs(Protocol):
    """Diretório de dados de cada pack, `<raiz>/<nome>` (ADR-041, research R62). Sem raiz, `None` nos dois."""

    def path(self, pack: str) -> Path | None:
        """O caminho, sem tocar o disco: a carga o entrega no `PackContext`."""
        ...

    def create(self, pack: str) -> Path | None:
        """Cria o diretório (com os pais; já existir não é erro) e o devolve: só o `packs prepare` chama."""
        ...
