"""Diretórios de dados dos packs no sistema de arquivos local (porta `PackDataDirs`; ADR-041, research R62)."""

from __future__ import annotations

from pathlib import Path


class LocalPackDataDirs:
    """`<raiz>/<nome do pack>`. O nome já passou pela regra de identidade da 001, então é um segmento seguro."""

    def __init__(self, root: Path | None) -> None:
        self._root = root

    def path(self, pack: str) -> Path | None:
        return self._root / pack if self._root is not None else None

    def create(self, pack: str) -> Path | None:
        directory = self.path(pack)
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
        return directory
