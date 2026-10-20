"""`TokenGenerator` real: o módulo `secrets` da biblioteca padrão."""

from __future__ import annotations

import secrets


class SecretsTokenGenerator:
    """Aleatoriedade criptográfica do sistema operacional."""

    def token_hex(self, nbytes: int) -> str:
        return secrets.token_hex(nbytes)

    def token_urlsafe(self, nbytes: int) -> str:
        return secrets.token_urlsafe(nbytes)
