"""T022 — conformidade da porta `McpServerStore` (contracts/ports.md): memória e Postgres (ADR-015)."""

from __future__ import annotations

from typing import Any

import pytest
from mcp_testkit import T0, global_draft, policy, user_draft

from ai_core.mcp.ports import StoredServer

pytestmark = pytest.mark.us2


def record(owner: str | None = None, **overrides: Any) -> StoredServer:
    draft = user_draft(**overrides) if owner is not None else global_draft(**overrides)
    return StoredServer(owner=owner, draft=draft, created_at=T0, updated_at=T0)


async def test_insert_get_e_duplicado(server_store: Any) -> None:
    assert await server_store.insert(record())
    assert not await server_store.insert(record(description="outra")), "(owner, alias) já existe"
    stored = await server_store.get(None, "financeiro")
    assert stored is not None and stored.draft.description == "Saldos e extratos"
    assert await server_store.get("user:ana", "financeiro") is None


async def test_o_rascunho_volta_igual(server_store: Any) -> None:
    original = record(
        auth_type="bearer",
        credential_ref="financeiro_token",
        user_access=True,
        enabled=False,
        policy=policy(allowed_tools=("a", "b"), write_tools=("b",), timeout_ms=5000, max_response_bytes=2048),
    )
    await server_store.insert(original)
    stored = await server_store.get(None, "financeiro")
    assert stored is not None
    assert stored.draft == original.draft
    assert (stored.created_at, stored.updated_at) == (T0, T0)


async def test_replace_e_delete(server_store: Any) -> None:
    assert not await server_store.replace(record())
    assert not await server_store.delete(None, "financeiro")
    await server_store.insert(record())
    assert await server_store.replace(record(description="nova"))
    stored = await server_store.get(None, "financeiro")
    assert stored is not None and stored.draft.description == "nova"
    assert await server_store.delete(None, "financeiro")
    assert await server_store.get(None, "financeiro") is None


async def test_list_por_dono_e_all(server_store: Any) -> None:
    await server_store.insert(record())
    await server_store.insert(record(alias="b-global"))
    await server_store.insert(record("user:ana"))
    await server_store.insert(record("user:ana", alias="~outro"))
    await server_store.insert(record("user:bia"))

    assert [r.alias for r in await server_store.list(None)] == ["b-global", "financeiro"]
    assert [r.alias for r in await server_store.list("user:ana")] == ["~drive", "~outro"]
    assert [(r.owner, r.alias) for r in await server_store.list("user:bia")] == [("user:bia", "~drive")]
    assert len(await server_store.all()) == 5


async def test_o_mesmo_alias_em_donos_diferentes(server_store: Any) -> None:
    assert await server_store.insert(record("user:ana"))
    assert await server_store.insert(record("user:bia"))
