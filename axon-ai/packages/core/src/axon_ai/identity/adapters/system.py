"""`TokenGenerator` real, sobre `secrets` (research R10). O relógio do sistema é o da 011."""

from __future__ import annotations

import secrets
import uuid

from axon_ai.identity.domain.accounts import PASSWORD_ALPHABET, group_password


class SystemTokenGenerator:
    def token(self, nbytes: int = 32) -> str:
        return secrets.token_urlsafe(nbytes)

    def uuid(self) -> str:
        return str(uuid.uuid4())

    def password(self) -> str:
        return group_password("".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(20)))
