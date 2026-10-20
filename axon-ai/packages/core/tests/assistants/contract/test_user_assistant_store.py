"""T039 — conformidade da porta `UserAssistantStore` (contracts/ports.md), em memória e contra Postgres."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from assistants_testkit import T0, draft

from axon_ai.assistants.ports import StoredUserAssistant


def _stored(owner: str = "user:ana", name: str = "meu-rag", **overrides: Any) -> StoredUserAssistant:
    return StoredUserAssistant(owner=owner, draft=draft(name, **overrides), created_at=T0, updated_at=T0)


async def test_unicidade_por_dono_e_nome(user_assistant_store: Any) -> None:
    assert await user_assistant_store.insert(_stored())
    assert not await user_assistant_store.insert(_stored(description="outra"))
    assert await user_assistant_store.insert(_stored(owner="user:bia"))


async def test_leitura_isolada_por_dono(user_assistant_store: Any) -> None:
    await user_assistant_store.insert(_stored("user:ana", "b"))
    await user_assistant_store.insert(_stored("user:ana", "a"))
    await user_assistant_store.insert(_stored("user:bia", "a"))

    assert [r.name for r in await user_assistant_store.list("user:ana")] == ["a", "b"]
    assert [r.name for r in await user_assistant_store.list("user:bia")] == ["a"]
    assert (await user_assistant_store.get("user:bia", "a")).owner == "user:bia"
    assert await user_assistant_store.get("user:bia", "b") is None
    assert [(r.owner, r.name) for r in await user_assistant_store.all()] == [
        ("user:ana", "a"),
        ("user:ana", "b"),
        ("user:bia", "a"),
    ]


async def test_ida_e_volta_do_rascunho_sem_perda(user_assistant_store: Any) -> None:
    completo = _stored(
        description="meu assistente",
        flow="chat",
        packs=("generic", "rag"),
        mcp=("agenda",),
        collections=("docs",),
        models={"generation": "ollama/qwen3:1.7b", "controller": "openrouter/qwen/qwen3-8b"},
        limits={"rpm": 5, "max_context_tokens": 2000},
        allowed_tools=("calculate",),
        write_tools=("criar-evento",),
    )
    minimo = _stored(name="minimo")
    for record in (completo, minimo):
        await user_assistant_store.insert(record)
        assert await user_assistant_store.get(record.owner, record.name) == record


async def test_substituir_e_remover(user_assistant_store: Any) -> None:
    await user_assistant_store.insert(_stored())
    novo = StoredUserAssistant(
        owner="user:ana", draft=draft(description="v2"), created_at=T0, updated_at=T0 + timedelta(minutes=1)
    )
    assert await user_assistant_store.replace(novo)
    assert await user_assistant_store.get("user:ana", "meu-rag") == novo

    assert await user_assistant_store.delete("user:ana", "meu-rag")
    assert await user_assistant_store.get("user:ana", "meu-rag") is None


async def test_substituir_ou_remover_inexistente_devolve_false(user_assistant_store: Any) -> None:
    assert not await user_assistant_store.replace(_stored())
    assert not await user_assistant_store.delete("user:ana", "meu-rag")


async def test_postgres_sobrevive_a_um_armazenamento_novo(migrated_pool: Any) -> None:
    """US6 cen. 3: vive no banco, não no processo — um adapter novo sobre o mesmo banco o encontra."""
    from axon_ai.assistants.adapters.assistants_postgres import PostgresUserAssistantStore

    await PostgresUserAssistantStore(migrated_pool).insert(_stored())
    assert await PostgresUserAssistantStore(migrated_pool).get("user:ana", "meu-rag") == _stored()
