"""Configuração do operador (specs/011-core-bootstrap/contracts/configuration.md).

A validação é pura e acontece **antes** da primeira etapa do boot: erro de configuração nomeia o campo e impede o
serviço de subir (FR-001, SC-002).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

MEMORY_PROFILE: Final = "memory"
TEST_PROFILE: Final = "test"
PROFILES: Final = (MEMORY_PROFILE, TEST_PROFILE)

DEFAULT_OLLAMA_BASE_URL: Final = "http://localhost:11434/v1"
DEFAULT_HOST: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8000
DEFAULT_SHUTDOWN_GRACE: Final = 10.0

PREFIX: Final = "AI_CORE_"


class ConfigurationError(ValueError):
    """Configuração inválida. A mensagem sempre nomeia o campo ou a variável."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    """O que o operador escolheu. Validada na construção."""

    profile: str = MEMORY_PROFILE
    packs_file: Path | None = None
    assistants_file: Path | None = None
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    trace_dir: Path | None = None
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    shutdown_grace_seconds: float = DEFAULT_SHUTDOWN_GRACE

    def __post_init__(self) -> None:
        if self.profile not in PROFILES:
            known = ", ".join(PROFILES)
            raise ConfigurationError(f"{PREFIX}PROFILE: perfil '{self.profile}' não existe; disponíveis: {known}")
        if not 1 <= self.port <= 65535:
            raise ConfigurationError(f"{PREFIX}PORT: porta fora da faixa 1-65535: {self.port}")
        if self.shutdown_grace_seconds < 0:
            raise ConfigurationError(
                f"{PREFIX}SHUTDOWN_GRACE_SECONDS: prazo não pode ser negativo: {self.shutdown_grace_seconds}"
            )
        if not self.ollama_base_url.strip():
            raise ConfigurationError(f"{PREFIX}OLLAMA_BASE_URL não pode ser vazio")


class InMemoryConfigSource:
    """Configuração pronta — o adapter em memória da porta."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings(profile=TEST_PROFILE)

    def load(self) -> Settings:
        return self._settings


class EnvConfigSource:
    """Configuração a partir das variáveis `AI_CORE_*` (contracts/configuration.md)."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = dict(environ if environ is not None else os.environ)

    def load(self) -> Settings:
        return Settings(
            profile=self._text("PROFILE", MEMORY_PROFILE),
            packs_file=self._path("PACKS_FILE"),
            assistants_file=self._path("ASSISTANTS_FILE"),
            ollama_base_url=self._text("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            trace_dir=self._path("TRACE_DIR"),
            host=self._text("HOST", DEFAULT_HOST),
            port=self._int("PORT", DEFAULT_PORT),
            shutdown_grace_seconds=self._float("SHUTDOWN_GRACE_SECONDS", DEFAULT_SHUTDOWN_GRACE),
        )

    def _text(self, name: str, default: str) -> str:
        return self._environ.get(f"{PREFIX}{name}", default)

    def _path(self, name: str) -> Path | None:
        raw = self._environ.get(f"{PREFIX}{name}")
        return Path(raw) if raw else None

    def _int(self, name: str, default: int) -> int:
        raw = self._environ.get(f"{PREFIX}{name}")
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError as error:
            raise ConfigurationError(f"{PREFIX}{name}: precisa ser um número inteiro: {raw!r}") from error

    def _float(self, name: str, default: float) -> float:
        raw = self._environ.get(f"{PREFIX}{name}")
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError as error:
            raise ConfigurationError(f"{PREFIX}{name}: precisa ser um número: {raw!r}") from error
