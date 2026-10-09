"""T039 — conformidade das portas `McpDirectory` e `CollectionCatalog` (contracts/ports.md)."""

from __future__ import annotations

from ai_core.assistants.adapters.catalogs import EmptyCollectionCatalog, EmptyMcpDirectory, PackCollectionCatalog
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


async def test_colecoes_dos_retrievers_dos_packs_habilitados() -> None:
    """005 Fase 5 (passada de encaixe da 011): o catálogo de coleções vem do Pack Registry."""
    from ai_core.packs.api import PackCapabilities, PackEntry, PackStatus, RetrieverCapability

    def entry(name: str, status: PackStatus, *collections: frozenset[str]) -> PackEntry:
        capabilities = PackCapabilities(
            system_prompt=False,
            tools=(),
            retrievers=tuple(RetrieverCapability(name=f"r{i}", collections=c) for i, c in enumerate(collections)),
            reranker=False,
            validators=(),
            preferred_flow=None,
            depends_on=(),
            requires_collections=(),
        )
        error = "quebrado" if status is PackStatus.ERROR else None
        return PackEntry(
            name=name,
            version="0.1.0",
            contract_version="0.1",
            origin="code",
            status=status,
            error=error,
            capabilities=capabilities if status is PackStatus.ENABLED else None,
        )

    class Registry:
        def entries(self) -> list[PackEntry]:
            return [
                entry("scouting", PackStatus.ENABLED, frozenset({"scouting"}), frozenset({"scouting", "atas"})),
                entry("desligado", PackStatus.DISABLED),
                entry("quebrado", PackStatus.ERROR),
                entry("generic", PackStatus.ENABLED),
            ]

    assert await PackCollectionCatalog(Registry()).names() == frozenset({"scouting", "atas"})  # type: ignore[arg-type]
