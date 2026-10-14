"""`ClientSource` real: o `identity.yaml` do operador (contracts/identity-yaml.md), lido uma vez no boot pela 011."""

from __future__ import annotations

from pathlib import Path

import yaml

from ai_core.identity.domain.clients import ClientsFileError, read_clients
from ai_core.identity.ports import Client


class YamlClientSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> tuple[Client, ...]:
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as error:
            raise ClientsFileError(f"{self._path}: não foi possível ler o arquivo: {error.strerror}") from None
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise ClientsFileError(f"{self._path}: YAML inválido: {error}") from None
        return read_clients(data, origin=str(self._path))
