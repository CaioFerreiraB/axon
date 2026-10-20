"""PackSource por entry points do empacotamento Python (FR-001, ADR-003)."""

from __future__ import annotations

import importlib.metadata
from collections.abc import Sequence

from axon_ai.packs.ports import DiscoveredPack

PACKS_GROUP = "axon.packs"


class EntryPointPackSource:
    """Lista os entry points do grupo `axon.packs`, sem importar os packs (o import acontece em `load()`)."""

    def __init__(self, group: str = PACKS_GROUP) -> None:
        self._group = group

    def discover(self) -> Sequence[DiscoveredPack]:
        found = []
        for entry_point in importlib.metadata.entry_points(group=self._group):
            distribution = entry_point.dist
            found.append(
                DiscoveredPack(
                    name=entry_point.name,
                    distribution=distribution.name if distribution is not None else "?",
                    version=distribution.version if distribution is not None else "?",
                    load=entry_point.load,
                )
            )
        return tuple(sorted(found, key=lambda pack: (pack.name, pack.distribution)))
