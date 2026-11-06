"""T021 — conformidade da porta `ApiKeyStore` (contracts/ports.md), em memória e contra Postgres."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from assistants_testkit import T0

from axon_ai.assistants.api import ApiKeyInfo
from axon_ai.assistants.domain.keys import ApiKeyRecord, hash_key


def _record(
    key_id: str,
    *,
    subject: str = "user:caio",
    at: Any = T0,
    groups: frozenset[str] = frozenset(),
    scopes: frozenset[str] = frozenset({"inference"}),
) -> ApiKeyRecord:
    info = ApiKeyInfo(
        key_id=key_id,
        subject=subject,
        groups=groups,
        label="notebook",
        created_at=at,
        scopes=scopes,  # type: ignore[arg-type]
    )
    return ApiKeyRecord(info=info, key_hash=hash_key(f"axn_{key_id}_segredo"))


async def test_guarda_e_le_pelo_key_id(api_key_store: Any) -> None:
    record = _record("00000000000000a1", groups=frozenset({"operadores", "leitores"}))
    await api_key_store.add(record)

    lido = await api_key_store.get("00000000000000a1")
    assert lido == record
    assert lido.key_hash == hash_key("axn_00000000000000a1_segredo")
    assert await api_key_store.get("00000000000000ff") is None


async def test_guarda_o_hash_nunca_a_chave(api_key_store: Any) -> None:
    record = _record("00000000000000a2")
    await api_key_store.add(record)
    lido = await api_key_store.get("00000000000000a2")
    assert "segredo" not in repr(lido.info)
    assert not hasattr(lido, "plaintext")


async def test_revogacao_e_idempotente_e_preserva_o_primeiro_instante(api_key_store: Any) -> None:
    await api_key_store.add(_record("00000000000000a3"))
    primeira = await api_key_store.revoke("00000000000000a3", at=T0 + timedelta(minutes=1))
    segunda = await api_key_store.revoke("00000000000000a3", at=T0 + timedelta(minutes=5))

    assert primeira.info.revoked_at == T0 + timedelta(minutes=1)
    assert segunda.info.revoked_at == T0 + timedelta(minutes=1)
    assert (await api_key_store.get("00000000000000a3")).info.revoked_at == T0 + timedelta(minutes=1)


async def test_revogar_inexistente_devolve_none(api_key_store: Any) -> None:
    assert await api_key_store.revoke("00000000000000ff", at=T0) is None


async def test_lista_inclui_revogadas_em_ordem_de_emissao(api_key_store: Any) -> None:
    await api_key_store.add(_record("00000000000000b2", at=T0 + timedelta(minutes=2)))
    await api_key_store.add(_record("00000000000000b1", at=T0 + timedelta(minutes=1)))
    await api_key_store.revoke("00000000000000b2", at=T0 + timedelta(minutes=3))

    listadas = await api_key_store.list()
    assert [r.info.key_id for r in listadas] == ["00000000000000b1", "00000000000000b2"]
    assert [r.info.active for r in listadas] == [True, False]


# --- US12: rotação (research R38) ------------------------------------------------------------------------------------


@pytest.mark.us12
async def test_rotacao_troca_o_hash_e_preserva_o_resto(api_key_store: Any) -> None:
    record = _record("00000000000000c1", subject="svc:relatorios", groups=frozenset({"leitores"}))
    await api_key_store.add(record)
    novo = hash_key("axn_00000000000000c1_outro")

    rotacionada = await api_key_store.rotate("00000000000000c1", key_hash=novo, at=T0 + timedelta(minutes=1))

    assert rotacionada.key_hash == novo
    assert rotacionada.info.rotated_at == T0 + timedelta(minutes=1)
    for campo in ("key_id", "subject", "groups", "label", "created_at", "revoked_at"):
        assert getattr(rotacionada.info, campo) == getattr(record.info, campo)
    assert await api_key_store.get("00000000000000c1") == rotacionada


@pytest.mark.us12
async def test_rotacao_de_novo_troca_de_novo(api_key_store: Any) -> None:
    await api_key_store.add(_record("00000000000000c2"))
    await api_key_store.rotate("00000000000000c2", key_hash=hash_key("a"), at=T0 + timedelta(minutes=1))
    segunda = await api_key_store.rotate("00000000000000c2", key_hash=hash_key("b"), at=T0 + timedelta(minutes=2))

    assert segunda.key_hash == hash_key("b")
    assert segunda.info.rotated_at == T0 + timedelta(minutes=2)


@pytest.mark.us12
async def test_chave_revogada_nao_rotaciona_e_continua_como_estava(api_key_store: Any) -> None:
    record = _record("00000000000000c3")
    await api_key_store.add(record)
    revogada = await api_key_store.revoke("00000000000000c3", at=T0 + timedelta(minutes=1))

    assert await api_key_store.rotate("00000000000000c3", key_hash=hash_key("x"), at=T0 + timedelta(minutes=2)) is None
    lida = await api_key_store.get("00000000000000c3")
    assert lida == revogada
    assert lida.key_hash == record.key_hash and lida.info.rotated_at is None


@pytest.mark.us12
async def test_rotacionar_inexistente_devolve_none(api_key_store: Any) -> None:
    assert await api_key_store.rotate("00000000000000ff", key_hash=hash_key("x"), at=T0) is None


@pytest.mark.us12
async def test_lista_traz_o_instante_da_rotacao(api_key_store: Any) -> None:
    await api_key_store.add(_record("00000000000000c4"))
    await api_key_store.rotate("00000000000000c4", key_hash=hash_key("x"), at=T0 + timedelta(minutes=3))

    (listada,) = [r for r in await api_key_store.list() if r.info.key_id == "00000000000000c4"]
    assert listada.info.rotated_at == T0 + timedelta(minutes=3)


# --- US14: escopos (research R49) ------------------------------------------------------------------------------------


@pytest.mark.us14
async def test_escopos_na_ida_e_volta_e_na_rotacao(api_key_store: Any) -> None:
    record = _record("00000000000000f1", scopes=frozenset({"users", "inference"}))
    await api_key_store.add(record)

    assert (await api_key_store.get("00000000000000f1")).info.scopes == frozenset({"users", "inference"})
    assert [r.info.scopes for r in await api_key_store.list()] == [frozenset({"users", "inference"})]
    rotacionada = await api_key_store.rotate(
        "00000000000000f1", key_hash=hash_key("axn_00000000000000f1_x"), at=T0 + timedelta(minutes=1)
    )
    assert rotacionada.info.scopes == frozenset({"users", "inference"})


# --- US15: apagamento por subject (research R52) ---------------------------------------------------------------------


@pytest.mark.us15
async def test_erase_subject_apaga_ativas_e_revogadas_so_do_subject(api_key_store: Any) -> None:
    await api_key_store.add(_record("00000000000000f2", subject="user:ana"))
    await api_key_store.add(_record("00000000000000f3", subject="user:ana"))
    await api_key_store.add(_record("00000000000000f4", subject="user:bia"))
    await api_key_store.revoke("00000000000000f3", at=T0)

    assert await api_key_store.erase_subject("user:ana") == 2
    assert [r.info.key_id for r in await api_key_store.list()] == ["00000000000000f4"]
    assert await api_key_store.get("00000000000000f2") is None
    assert await api_key_store.erase_subject("user:ana") == 0
