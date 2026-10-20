"""Chaves de API: formato, hash e comparação (research R7).

Formato `axn_<key_id>_<segredo>`: o `key_id` (8 bytes em hexadecimal) é público e serve para listar e revogar; o
segredo tem 32 bytes. Guarda-se o SHA-256 da chave inteira: com 256 bits de entropia, um hash rápido basta — KDF lenta
é para senha escolhida por gente.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Final

from axon_ai.assistants.api import KEY_ID_PATTERN, ApiKeyInfo

KEY_PREFIX: Final = "axn_"
KEY_ID_BYTES: Final = 8
SECRET_BYTES: Final = 32


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiKeyRecord:
    """O que o armazenamento guarda: os dados mostráveis e o hash — nunca a chave."""

    info: ApiKeyInfo
    key_hash: bytes


def compose_key(key_id: str, secret: str) -> str:
    return f"{KEY_PREFIX}{key_id}_{secret}"


def parse_key(text: str) -> str | None:
    """O `key_id` de uma chave bem formada, ou `None`. Não diz nada sobre a chave existir."""
    if not text.startswith(KEY_PREFIX) or any(char.isspace() for char in text):
        return None
    key_id, separator, secret = text.removeprefix(KEY_PREFIX).partition("_")
    if not separator or not secret or not KEY_ID_PATTERN.fullmatch(key_id):
        return None
    return key_id


def hash_key(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def matches(text: str, key_hash: bytes) -> bool:
    """Comparação em tempo constante: o tempo de resposta não revela quantos bytes do hash coincidem."""
    return hmac.compare_digest(hash_key(text), key_hash)
