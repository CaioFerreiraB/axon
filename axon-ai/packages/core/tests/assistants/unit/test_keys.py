"""T019 — formato, hash e comparação de chaves de API (research R7)."""

from __future__ import annotations

import hashlib

import pytest

from axon_ai.assistants.domain import keys as keys_module
from axon_ai.assistants.domain.keys import compose_key, hash_key, matches, parse_key

KEY_ID = "0123456789abcdef"


def test_chave_composta_e_lida_de_volta() -> None:
    chave = compose_key(KEY_ID, "Jd8-_x")
    assert chave == f"axn_{KEY_ID}_Jd8-_x"
    assert parse_key(chave) == KEY_ID


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "abc",
        "axn_",
        f"axn_{KEY_ID}",
        f"axn_{KEY_ID}_",
        "axn_XYZ_segredo",
        "axn_0123456789ABCDEF_segredo",
        "axn_0123456789abcde_segredo",
        f"xyz_{KEY_ID}_segredo",
        f"Bearer axn_{KEY_ID}_segredo",
        f"axn_{KEY_ID}_seg redo",
        f"aic_{KEY_ID}_segredo",  # o prefixo antigo: corte seco (ADR-037, US11)
    ],
)
def test_chave_fora_do_formato_nao_tem_key_id(texto: str) -> None:
    assert parse_key(texto) is None


def test_hash_e_sha256_da_chave_inteira() -> None:
    chave = compose_key(KEY_ID, "segredo")
    assert hash_key(chave) == hashlib.sha256(chave.encode()).digest()


def test_comparacao_em_tempo_constante(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[bytes, bytes]] = []
    original = keys_module.hmac.compare_digest

    def espiao(a: bytes, b: bytes) -> bool:
        chamadas.append((a, b))
        return original(a, b)

    monkeypatch.setattr(keys_module.hmac, "compare_digest", espiao)
    chave = compose_key(KEY_ID, "segredo")
    assert matches(chave, hash_key(chave))
    assert not matches(chave + "x", hash_key(chave))
    assert len(chamadas) == 2
