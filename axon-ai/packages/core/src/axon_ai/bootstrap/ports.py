"""Porta secundária da composition root: de onde vem a configuração do operador."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from axon_ai.bootstrap.settings import Settings


class ConfigSource(Protocol):
    """Origem da configuração. Existe por I/O: ambiente e arquivos montados na imagem (ADR-009)."""

    def load(self) -> Settings:
        """Configuração validada. Levanta `ConfigurationError` nomeando o campo inválido."""
        ...
