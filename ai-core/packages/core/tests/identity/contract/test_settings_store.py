"""T011 — conformidade do `IdentitySettingsStore` (memória e Postgres): padrão, gravação e versão otimista."""

from __future__ import annotations

from typing import Any

from identity_testkit import T0

from ai_core.identity.ports import IdentitySettings


async def test_sem_gravacao_e_o_padrao_e_a_versao_protege_a_escrita(stores: Any) -> None:
    store = stores.settings
    assert await store.get() == IdentitySettings()
    first = IdentitySettings(google_enabled=False, version=1, updated_by="user:admin", updated_at=T0)
    assert await store.put(first, expected_version=0) is True
    assert await store.get() == first
    assert await store.put(IdentitySettings(google_enabled=True, version=1), expected_version=0) is False
    second = IdentitySettings(google_enabled=None, version=2, updated_by="cli", updated_at=T0)
    assert await store.put(second, expected_version=1) is True
    assert await store.put(IdentitySettings(google_enabled=True, version=2), expected_version=1) is False
    assert await store.get() == second
