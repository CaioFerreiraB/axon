"""PackConfigSource a partir do `packs.yaml` do operador (specs/002-core-pack-runtime/contracts/packs-yaml.md).

O formato é da 002; o caminho do arquivo e a escolha deste adapter são da composition root (spec 011).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from ai_core.packs.api import PackConfigError
from ai_core.packs.domain.config import is_json
from ai_core.packs.ports import PackSettings

_PACK_KEYS = frozenset({"enabled", "config"})


class YamlPackConfigSource:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def load(self) -> Mapping[str, PackSettings]:
        data = self._read()
        if not isinstance(data, dict) or "packs" not in data:
            raise PackConfigError(f"{self._path}: a raiz precisa ser um mapeamento com a chave 'packs'")
        unknown = sorted(str(key) for key in data if key != "packs")
        if unknown:
            raise PackConfigError(f"{self._path}: chave desconhecida na raiz: {', '.join(unknown)}")
        packs = data["packs"] if data["packs"] is not None else {}
        if not isinstance(packs, dict):
            raise PackConfigError(f"{self._path}: 'packs' precisa ser um mapeamento de nome → configuração")
        return {str(name): self._settings(str(name), raw) for name, raw in packs.items()}

    def _read(self) -> Any:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise PackConfigError(f"arquivo de configuração de packs não encontrado: {self._path}") from error
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise PackConfigError(f"{self._path}: YAML inválido: {error}") from error

    def _settings(self, name: str, raw: object) -> PackSettings:
        where = f"packs.{name}"
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise PackConfigError(f"{self._path}: {where} precisa ser um mapeamento")
        unknown = sorted(str(key) for key in raw if key not in _PACK_KEYS)
        if unknown:
            raise PackConfigError(f"{self._path}: {where}.{unknown[0]}: chave desconhecida (use 'enabled' e 'config')")
        enabled = raw.get("enabled", False)
        if not isinstance(enabled, bool):
            raise PackConfigError(f"{self._path}: {where}.enabled precisa ser booleano")
        config = raw.get("config") if raw.get("config") is not None else {}
        if not isinstance(config, dict) or not is_json(config):
            raise PackConfigError(f"{self._path}: {where}.config precisa ser um mapeamento com valores JSON")
        return PackSettings(enabled=enabled, config=config)
