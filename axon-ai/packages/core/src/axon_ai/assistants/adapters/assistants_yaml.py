"""`AssistantConfigSource` a partir do `assistants.yaml` do operador (contracts/assistants-yaml.md).

Só lê o arquivo e o YAML: a interpretação é do domínio, a mesma do adapter em memória — é o que garante que boot,
`assistants validate` e suítes digam a mesma coisa sobre o mesmo arquivo.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from axon_ai.assistants.api import AssistantsConfigError
from axon_ai.assistants.domain.definitions import AssistantsConfig, read_config


class YamlAssistantConfigSource:
    """Lê o arquivo uma vez por `load()`. Erro de leitura ou de YAML é erro de arquivo: o boot para."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> AssistantsConfig:
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as error:
            raise AssistantsConfigError(f"arquivo de assistants não pôde ser lido: {self._path}: {error}") from error
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise AssistantsConfigError(f"{self._path}: YAML inválido: {error}") from error
        return read_config(data, origin=str(self._path))
