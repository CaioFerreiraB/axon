"""T014 — `SecretCipher`: AES-GCM com subchave HKDF própria da 012 (ADR-033)."""

from __future__ import annotations

import pytest
from identity_testkit import MASTER_KEY

from axon_ai.identity.adapters.cipher import AesGcmCipher
from axon_ai.identity.ports import SealError


def test_ida_e_volta_com_nonce_novo_a_cada_selo() -> None:
    cipher = AesGcmCipher(MASTER_KEY)
    first, second = cipher.seal(b"chave privada"), cipher.seal(b"chave privada")
    assert first != second
    assert b"chave privada" not in first
    assert cipher.open(first) == cipher.open(second) == b"chave privada"


def test_chave_mestra_errada_falha_sem_vazar_o_texto() -> None:
    sealed = AesGcmCipher(MASTER_KEY).seal(b"segredo")
    with pytest.raises(SealError) as caught:
        AesGcmCipher(bytes(32)).open(sealed)
    assert "segredo" not in str(caught.value)


def test_subchave_de_outro_modulo_nao_abre() -> None:
    sealed = AesGcmCipher(MASTER_KEY).seal(b"segredo")
    with pytest.raises(SealError):
        AesGcmCipher(MASTER_KEY, info=b"axon-ai/observability/v1").open(sealed)


@pytest.mark.parametrize("tamper", [lambda s: s[:-1] + bytes([s[-1] ^ 1]), lambda s: b"\x02" + s[1:], lambda s: s[:10]])
def test_selo_adulterado_falha(tamper: object) -> None:
    cipher = AesGcmCipher(MASTER_KEY)
    sealed = cipher.seal(b"segredo")
    assert callable(tamper)
    with pytest.raises(SealError):
        cipher.open(tamper(sealed))


def test_chave_mestra_precisa_de_32_bytes() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        AesGcmCipher(b"curta")
