"""`PasswordHasher` real: argon2id com `argon2-cffi` (research R2).

Perfil RFC 9106 de baixa memória (t=3, m=64 MiB, p=4). O cálculo vai para uma thread: ~100 ms de CPU não podem
parar o laço de eventos. O hash fictício de quem não existe é calculado uma vez, com os mesmos parâmetros, para que
"usuário inexistente" custe o mesmo que "senha errada" (FR-003, SC-005).
"""

from __future__ import annotations

import asyncio
import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    def __init__(self, *, time_cost: int = 3, memory_cost: int = 64 * 1024, parallelism: int = 4) -> None:
        self._hasher = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy = self._hasher.hash(secrets.token_urlsafe(16))

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password_hash: str, password: str) -> bool:
        try:
            return await asyncio.to_thread(self._hasher.verify, password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True

    async def dummy_verify(self, password: str) -> None:
        await self.verify(self._dummy, password)
