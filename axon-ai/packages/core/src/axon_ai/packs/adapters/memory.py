"""Adapters em memória das portas da 002 — testes e perfil `test` da composition root."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from axon_ai.packs.api import PackConfigError
from axon_ai.packs.ports import DiscoveredPack, PackSettings


def _loader(target: object) -> Callable[[], object]:
    def load() -> object:
        return target

    return load


class InMemoryPackSource:
    """Packs "instalados" em memória."""

    def __init__(self, entries: Sequence[DiscoveredPack] = ()) -> None:
        self._entries = tuple(entries)

    @classmethod
    def of(
        cls, *items: type | tuple[str, object], distribution: str = "test-dist", version: str = "0.1.0"
    ) -> InMemoryPackSource:
        """Uma entrada por classe (nome do entry point = `cls.name`) ou por par `(nome, classe)`."""
        entries: list[DiscoveredPack] = []
        for item in items:
            if isinstance(item, tuple):
                name, target = item
            else:
                name, target = str(getattr(item, "name", item.__name__)), item
            entries.append(
                DiscoveredPack(name=name, distribution=f"{distribution}-{name}", version=version, load=_loader(target))
            )
        return cls(entries)

    def discover(self) -> Sequence[DiscoveredPack]:
        return self._entries


class InMemoryPackConfigSource:
    """Configuração de packs em memória; `error` simula arquivo malformado."""

    def __init__(
        self, settings: Mapping[str, PackSettings] | None = None, *, error: PackConfigError | None = None
    ) -> None:
        self._settings = dict(settings or {})
        self._error = error

    def load(self) -> Mapping[str, PackSettings]:
        if self._error is not None:
            raise self._error
        return dict(self._settings)
