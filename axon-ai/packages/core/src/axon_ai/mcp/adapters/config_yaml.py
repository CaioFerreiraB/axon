"""`McpConfigSource` a partir do `mcp.yaml` do operador (contracts/mcp-yaml.md).

Este adapter só lê o arquivo e o YAML; o formato e as regras são do domínio (`read_config`), as mesmas do adapter em
memória — a mensagem de erro não diverge entre os dois.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from axon_ai.mcp.api import McpConfigError
from axon_ai.mcp.domain.servers import read_config
from axon_ai.mcp.ports import McpConfig


class YamlMcpConfigSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> McpConfig:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise McpConfigError(f"arquivo do operador não encontrado: {self._path}") from None
        except OSError as error:
            raise McpConfigError(f"{self._path}: não foi possível ler: {error.strerror}") from None
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise McpConfigError(f"{self._path}: YAML inválido: {error}") from None
        return read_config(data, origin=str(self._path))
