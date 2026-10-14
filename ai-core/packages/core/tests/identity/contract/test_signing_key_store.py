"""T011 — conformidade do `SigningKeyStore` (memória e Postgres): ordem, estados e a privada só selada."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from identity_testkit import T0

from ai_core.identity.api import Conflict
from ai_core.identity.ports import SigningKey


def _key(kid: str, minutes: int = 0) -> SigningKey:
    return SigningKey(
        kid=kid,
        public_jwk={"kty": "RSA", "kid": kid, "n": "abc", "e": "AQAB"},
        private_sealed=b"\x01selado" + kid.encode(),
        state="active",
        created_at=T0 + timedelta(minutes=minutes),
    )


async def test_guarda_em_ordem_de_criacao_e_muda_estado(stores: Any) -> None:
    keys = stores.keys
    await keys.put(_key("b", minutes=1))
    await keys.put(_key("a"))
    assert [key.kid for key in await keys.all()] == ["a", "b"]
    at = T0 + timedelta(hours=1)
    await keys.set_state("a", "retiring", at=at)
    retiring = (await keys.all())[0]
    assert retiring.state == "retiring" and retiring.retiring_since == at
    await keys.set_state("a", "retired", at=at + timedelta(hours=1))
    retired = (await keys.all())[0]
    assert retired.state == "retired" and retired.retiring_since == at
    assert retired.private_sealed == b"\x01seladoa"
    assert dict(retired.public_jwk) == {"kty": "RSA", "kid": "a", "n": "abc", "e": "AQAB"}


async def test_kid_repetido_e_conflito(stores: Any) -> None:
    await stores.keys.put(_key("a"))
    with pytest.raises(Conflict):
        await stores.keys.put(_key("a"))
