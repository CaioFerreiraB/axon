"""T039 — conformidade das portas `McpDirectory` e `CollectionCatalog` (contracts/ports.md)."""

from __future__ import annotations

from ai_core.assistants.adapters.catalogs import EmptyCollectionCatalog, EmptyMcpDirectory
from ai_core.assistants.adapters.memory import InMemoryCollectionCatalog, InMemoryMcpDirectory


async def test_catalogos_vazios_da_fase() -> None:
    assert await EmptyMcpDirectory().aliases(owner=None) == frozenset()
    assert await EmptyMcpDirectory().aliases(owner="user:ana") == frozenset()
    assert await EmptyCollectionCatalog().names() == frozenset()


async def test_mcp_em_memoria_separa_globais_compartilhados_e_do_dono() -> None:
    directory = InMemoryMcpDirectory(
        global_aliases={"finance", "drive"},
        shared_with_users={"drive"},
        by_owner={"user:ana": {"agenda"}},
    )
    assert await directory.aliases(owner=None) == frozenset({"finance", "drive"})
    assert await directory.aliases(owner="user:ana") == frozenset({"agenda", "drive"})
    assert await directory.aliases(owner="user:bia") == frozenset({"drive"})


async def test_colecoes_em_memoria() -> None:
    assert await InMemoryCollectionCatalog({"docs"}).names() == frozenset({"docs"})
