"""Tools de escrita (FR-010; US4). Pura.

Uma tool que muta estado só entra no catálogo se o nome com namespace estiver em `write_tools`, comparado de forma
exata. Assistant público tem `write_tools` vazio sempre (003 FR-012), então nunca tem tool de escrita.
"""

from __future__ import annotations

from axon_ai.capabilities.api import CatalogTool


def allowed_to_write(tool: CatalogTool, write_tools: frozenset[str]) -> bool:
    return not tool.mutates or tool.name in write_tools
