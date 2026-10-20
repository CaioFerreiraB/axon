"""T019 — ciclo de vida das chaves de assinatura (FR-016; R7) e o início do serviço."""

from __future__ import annotations

from datetime import timedelta

import pytest
from identity_testkit import MASTER_KEY, T0, harness

from axon_ai.identity.adapters.cipher import AesGcmCipher
from axon_ai.identity.domain.keys import due_for_retirement, jwks, published, signing_key, to_retire_on_rotation
from axon_ai.identity.ports import SigningKey
from axon_ai.identity.service import IdentityStartError

GRACE = timedelta(minutes=11)


def _key(kid: str, state: str, minutes: int = 0, retiring_since: int | None = None) -> SigningKey:
    return SigningKey(
        kid=kid,
        public_jwk={"kid": kid},
        private_sealed=b"",
        state=state,  # type: ignore[arg-type]
        created_at=T0 + timedelta(minutes=minutes),
        retiring_since=T0 + timedelta(minutes=retiring_since) if retiring_since is not None else None,
    )


def test_assina_a_ativa_mais_recente_e_publica_ativas_e_em_retirada() -> None:
    keys = [_key("a", "retired"), _key("b", "retiring", 1, 2), _key("c", "active", 2), _key("d", "active", 3)]
    assert signing_key(keys).kid == "d"  # type: ignore[union-attr]
    assert [key.kid for key in published(keys)] == ["b", "c", "d"]
    assert jwks(keys) == {"keys": [{"kid": "b"}, {"kid": "c"}, {"kid": "d"}]}
    assert signing_key([_key("a", "retired")]) is None


def test_em_retirada_sai_depois_do_ttl_do_acesso_mais_a_tolerancia() -> None:
    keys = [_key("b", "retiring", 0, 0), _key("c", "active", 1)]
    assert due_for_retirement(keys, now=T0 + timedelta(minutes=10), grace=GRACE) == ()
    assert due_for_retirement(keys, now=T0 + GRACE, grace=GRACE) == ("b",)


def test_rotacao_normal_e_forcada() -> None:
    keys = [_key("a", "retired"), _key("b", "retiring", 1, 2), _key("c", "active", 2)]
    assert to_retire_on_rotation(keys, force=False) == (("c", "retiring"),)
    assert to_retire_on_rotation(keys, force=True) == (("b", "retired"), ("c", "retired"))


async def test_start_gera_uma_chave_selada_e_publica_o_jwks() -> None:
    parts = harness()
    await parts.service.start()
    stored = await parts.keys.all()
    assert len(stored) == 1 and stored[0].state == "active"
    assert b"PRIVATE KEY" not in stored[0].private_sealed
    assert AesGcmCipher(MASTER_KEY).open(stored[0].private_sealed).startswith(b"-----BEGIN PRIVATE KEY-----")
    assert parts.service.jwks() == {"keys": [dict(stored[0].public_jwk)]}
    assert "admin" in await parts.accounts.groups()
    # um segundo início reaproveita a chave
    await parts.service.start()
    assert len(await parts.keys.all()) == 1


async def test_chave_mestra_errada_para_o_inicio_com_orientacao() -> None:
    parts = harness()
    await parts.service.start()
    other = harness()
    other.keys = parts.keys
    other.service._keys = parts.keys  # mesma tabela, chave mestra diferente
    other.service._cipher = AesGcmCipher(bytes(32))
    with pytest.raises(IdentityStartError, match="keys rotate --force"):
        await other.service.start()


@pytest.mark.us8
def test_os_rotulos_sao_os_da_marca() -> None:
    import hashlib

    from axon_ai.identity.adapters.cipher import INFO
    from axon_ai.identity.domain.digest import session_csrf

    assert INFO == b"axon-ai/identity/v1"
    assert session_csrf("t") == hashlib.sha256(b"axon-ai/identity/csrf:t").hexdigest()


@pytest.mark.us8
async def test_chave_selada_antes_do_renome_para_o_inicio_e_a_rotacao_forcada_recupera() -> None:
    """US8 cen. 7 (ADR-037, corte seco): o rótulo antigo não abre; `rotate --force` não precisa abri-lo."""
    antigo = harness()
    antigo.service._cipher = AesGcmCipher(MASTER_KEY, info=b"ai-core/identity/v1")
    await antigo.service.start()
    novo = harness()
    novo.keys = antigo.keys
    novo.service._keys = antigo.keys
    with pytest.raises(IdentityStartError, match="antes do renome") as caught:
        await novo.service.start()
    assert "keys rotate --force" in str(caught.value)
    await novo.service.rotate_keys(force=True)
    await novo.service.start()
    assert novo.service.jwks()["keys"]
