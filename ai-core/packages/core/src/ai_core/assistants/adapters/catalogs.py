"""Catálogos de MCP e de coleções desta fase: vazios (clarificação de 2026-09-30, research R11).

A 007 (Fase 3) e o índice (Fase 5) entram como troca de adapter. Até lá, qualquer Assistant que declara MCP ou coleção
fica indisponível com erro que nomeia a referência — nunca resolvido com a referência ignorada.
"""

from __future__ import annotations


class EmptyMcpDirectory:
    """Nenhum alias MCP existe antes da 007."""

    async def aliases(self, *, owner: str | None) -> frozenset[str]:
        return frozenset()


class EmptyCollectionCatalog:
    """Nenhuma coleção existe antes do índice."""

    async def names(self) -> frozenset[str]:
        return frozenset()
