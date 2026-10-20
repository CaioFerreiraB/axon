"""T076 — conformidade do `SystemOverrideStore` (memória e Postgres; research R30): versão otimista e histórico na mesma
operação."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from typing import Any

import pytest
from assistants_testkit import T0

from axon_ai.assistants.api import Conflict
from axon_ai.assistants.domain.overrides import StoredOverride

pytestmark = pytest.mark.us10


def _record(section: str = "models", **changes: Any) -> StoredOverride:
    base = StoredOverride(
        assistant="geral",
        section=section,  # type: ignore[arg-type]
        payload={"roles": {"generation": "openrouter/a/b"}},
        fingerprint="f1",
        version=0,
        updated_by="user:root",
        updated_at=T0,
    )
    return dataclasses.replace(base, **changes)


async def test_gravar_ler_e_versao(override_store: Any) -> None:
    first = await override_store.put(_record(), expected_version=None)
    assert first.version == 1
    assert [r.version for r in await override_store.get("geral")] == [1]
    with pytest.raises(Conflict) as caught:
        await override_store.put(_record(), expected_version=None)
    assert caught.value.current_version == 1
    second = await override_store.put(
        _record(payload={"roles": {"generation": "openrouter/a/c"}}, updated_by="user:bia"), expected_version=1
    )
    assert second.version == 2
    (stored,) = await override_store.get("geral")
    assert stored.payload == {"roles": {"generation": "openrouter/a/c"}} and stored.updated_by == "user:bia"
    with pytest.raises(Conflict) as caught:
        await override_store.put(_record(), expected_version=1)
    assert caught.value.current_version == 2


async def test_varias_secoes_e_assistants(override_store: Any) -> None:
    await override_store.put(_record("mcp", payload={"aliases": [], "allowed": [], "write": []}), expected_version=None)
    await override_store.put(_record(), expected_version=None)
    await override_store.put(_record(assistant="outro"), expected_version=None)
    assert [(r.assistant, r.section) for r in await override_store.all()] == [
        ("geral", "mcp"),
        ("geral", "models"),
        ("outro", "models"),
    ]
    assert [r.section for r in await override_store.get("geral")] == ["mcp", "models"]


async def test_descartar_com_versao_e_historico(override_store: Any) -> None:
    await override_store.put(_record(), expected_version=None)
    await override_store.put(_record(updated_at=T0 + timedelta(minutes=1)), expected_version=1)
    with pytest.raises(Conflict):
        await override_store.delete("geral", "models", expected_version=1, actor="user:bia", at=T0)
    later = T0 + timedelta(minutes=2)
    assert await override_store.delete("geral", "models", expected_version=2, actor="user:bia", at=later) is True
    assert await override_store.get("geral") == []
    assert await override_store.delete("geral", "models", expected_version=2, actor="user:bia", at=later) is False
    history = await override_store.history("geral")
    assert [(h.action, h.version, h.actor) for h in history] == [
        ("discarded", 2, "user:bia"),
        ("saved", 2, "user:root"),
        ("saved", 1, "user:root"),
    ]
    assert history[0].payload is None and history[1].payload == {"roles": {"generation": "openrouter/a/b"}}
    assert await override_store.history("outro") == []
