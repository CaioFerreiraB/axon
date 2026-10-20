"""`SecretCipher` real: AES-GCM com subchave HKDF-SHA256 da chave mestra (ADR-033; research R7).

A subchave é própria da 012 (`info="axon-ai/identity/v1"`): nenhum outro módulo abre o que este selou, mesmo com a
mesma chave mestra. O selo é `versão (1 byte) ‖ nonce (12 bytes) ‖ texto cifrado + tag`, com a versão como dado
associado; um nonce aleatório por gravação.
"""

from __future__ import annotations

import os
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from axon_ai.identity.ports import SealError

INFO: Final = b"axon-ai/identity/v1"
_VERSION: Final = b"\x01"
_NONCE: Final = 12


class AesGcmCipher:
    def __init__(self, master_key: bytes, *, info: bytes = INFO) -> None:
        if len(master_key) != 32:
            raise ValueError("a chave mestra precisa ter 32 bytes")
        subkey = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(master_key)
        self._aead = AESGCM(subkey)

    def seal(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(_NONCE)
        return _VERSION + nonce + self._aead.encrypt(nonce, plaintext, _VERSION)

    def open(self, sealed: bytes) -> bytes:
        if len(sealed) < 1 + _NONCE + 16 or sealed[:1] != _VERSION:
            raise SealError("selo em formato desconhecido")
        nonce, body = sealed[1 : 1 + _NONCE], sealed[1 + _NONCE :]
        try:
            return self._aead.decrypt(nonce, body, _VERSION)
        except InvalidTag:
            raise SealError("o selo não abre com esta chave mestra") from None
