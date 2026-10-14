"""Ciclo de vida das chaves de assinatura (FR-016, FR-017; research R7).

`active` assina; `retiring` só verifica, até todo token assinado por ela ter vencido (TTL do acesso + tolerância);
`retired` sai do JWKS. A rotação normal não invalida nenhum token vigente (SC-007).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from ai_core.identity.domain.records import SigningKey


def signing_key(keys: Sequence[SigningKey]) -> SigningKey | None:
    """A chave que assina: a `active` mais recente."""
    active = [key for key in keys if key.state == "active"]
    return max(active, key=lambda key: key.created_at) if active else None


def published(keys: Sequence[SigningKey]) -> tuple[SigningKey, ...]:
    return tuple(key for key in keys if key.state in ("active", "retiring"))


def jwks(keys: Sequence[SigningKey]) -> dict[str, object]:
    return {"keys": [dict(key.public_jwk) for key in published(keys)]}


def due_for_retirement(keys: Sequence[SigningKey], *, now: datetime, grace: timedelta) -> tuple[str, ...]:
    """`kid` das chaves `retiring` cujo último token possível já venceu."""
    return tuple(
        key.kid
        for key in keys
        if key.state == "retiring" and key.retiring_since is not None and now >= key.retiring_since + grace
    )


def to_retire_on_rotation(keys: Sequence[SigningKey], *, force: bool) -> tuple[tuple[str, str], ...]:
    """(`kid`, novo estado) na rotação: normal manda as ativas para `retiring`; forçada retira tudo o que publica."""
    state = "retired" if force else "retiring"
    return tuple((key.kid, state) for key in keys if key.state == "active" or (force and key.state == "retiring"))
