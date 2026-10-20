"""Catálogos de MCP e de coleções (clarificação de 2026-09-30, research R11).

Os vazios valiam antes dos donos: qualquer Assistant que declarasse MCP ou coleção ficava indisponível com erro que
nomeia a referência — nunca resolvido com a referência ignorada. A 007 (Fase 3) entrou como troca de adapter do
diretório de MCP; na Fase 5, as coleções vêm do Pack Registry (`PackCollectionCatalog`): o índice mora no pack que o
declara, e o core só conhece as coleções pelos retrievers dos packs (contrato 001, `NamedRetriever.collections`).
"""

from __future__ import annotations

from axon_ai.packs.api import PackRegistry, PackStatus


class EmptyMcpDirectory:
    """Nenhum alias MCP existe antes da 007."""

    async def aliases(self, *, owner: str | None) -> frozenset[str]:
        return frozenset()


class EmptyCollectionCatalog:
    """Nenhuma coleção existe antes do índice."""

    async def names(self) -> frozenset[str]:
        return frozenset()


class PackCollectionCatalog:
    """Coleções que existem = as que os retrievers dos packs **habilitados** declaram (005 Fase 5; passada de encaixe
    da 011). Pack desligado ou em erro não oferece coleção, e o Assistant que a referencia fica indisponível."""

    def __init__(self, registry: PackRegistry) -> None:
        self._registry = registry

    async def names(self) -> frozenset[str]:
        return frozenset(
            collection
            for entry in self._registry.entries()
            if entry.status is PackStatus.ENABLED and entry.capabilities is not None
            for retriever in entry.capabilities.retrievers
            for collection in retriever.collections
        )
