"""T021 — conformidade da porta `ApiKeyStore` (contracts/ports.md), em memória e contra Postgres."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from assistants_testkit import T0

from ai_core.assistants.api import ApiKeyInfo
from ai_core.assistants.domain.keys import ApiKeyRecord, hash_key


def _record(
    key_id: str, *, subject: str = "user:caio", at: Any = T0, groups: frozenset[str] = frozenset()
) -> ApiKeyRecord:
    info = ApiKeyInfo(key_id=key_id, subject=subject, groups=groups, label="notebook", created_at=at)
    return ApiKeyRecord(info=info, key_hash=hash_key(f"aic_{key_id}_segredo"))


async def test_guarda_e_le_pelo_key_id(api_key_store: Any) -> None:
    record = _record("00000000000000a1", groups=frozenset({"operadores", "leitores"}))
    await api_key_store.add(record)

    lido = await api_key_store.get("00000000000000a1")
    assert lido == record
    assert lido.key_hash == hash_key("aic_00000000000000a1_segredo")
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
