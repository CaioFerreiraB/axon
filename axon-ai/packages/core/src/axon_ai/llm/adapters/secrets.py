"""Adapters da porta `SecretResolver` (contracts/ports.md, "Fase 3"; research R21).

O de ambiente lê exatamente a variável pedida — os únicos nomes que chegam aqui são os dos adapters remotos, então não
há prefixo a impor (ao contrário da 007, cujas referências vêm de configuração e da API). O em memória serve ao perfil
de teste e às suítes.
"""

from __future__ import annotations

import os
from collections.abc import Mapping


def _present(value: str | None) -> str | None:
    """Vazio ou só espaços conta como ausente: uma variável definida em branco não é credencial."""
    if value is None or not value.strip():
        return None
    return value


class EnvSecretResolver:
    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def resolve(self, name: str) -> str | None:
        if not name:
            return None
        return _present(self._environ.get(name))


class InMemorySecretResolver:
    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def resolve(self, name: str) -> str | None:
        if not name:
            return None
        return _present(self._values.get(name))
