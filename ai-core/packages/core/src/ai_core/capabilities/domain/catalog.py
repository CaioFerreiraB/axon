"""A montagem do catálogo de uma execução (research R3; FR-001 a FR-003, FR-010, FR-012). Pura.

Cada regra é uma redução do conjunto, na ordem do `design.md`: tools de pack, retrievers cujas coleções estão todas no
grant, tools de MCP com o namespace do alias, filtro exato por `allowed_tools`, política de escrita e esquema conferido.
O que sobra é o único universo que o controller conhece — e o que o gateway aceita executar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from ai_core.capabilities.api import CatalogConflict, CatalogTool
from ai_core.capabilities.domain.arguments import check_schema
from ai_core.capabilities.domain.records import PackTool
from ai_core.capabilities.domain.write_policy import allowed_to_write
from axon_ai_contracts import NamedRetriever, NativeHandler, ToolSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    """Uma tool do catálogo e o que o gateway precisa para despachá-la. Nunca sai do módulo."""

    tool: CatalogTool
    pack: str | None = None
    handler: NativeHandler | None = None
    retriever: NamedRetriever | None = None
    alias: str | None = None
    local_name: str
    trusted_schema: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Assembly:
    entries: Mapping[str, Entry] = field(default_factory=dict)
    invalid: tuple[tuple[str, str], ...] = ()
    """Tools que saíram por esquema inválido, com o motivo — vão para o trace."""


def assemble(
    pack_tools: Sequence[PackTool],
    mcp: Sequence[tuple[str, Sequence[ToolSpec]]],
    *,
    allowed: frozenset[str] | None,
    write: frozenset[str],
    collections: frozenset[str],
) -> Assembly:
    _refuse_conflicts(pack_tools, mcp)
    candidates = [_from_pack(tool) for tool in pack_tools if _collections_allowed(tool, collections)]
    candidates += [_from_mcp(alias, spec) for alias, specs in mcp for spec in specs]

    entries: dict[str, Entry] = {}
    invalid: list[tuple[str, str]] = []
    for entry in candidates:
        name = entry.tool.name
        if allowed is not None and name not in allowed:
            continue
        if not allowed_to_write(entry.tool, write):
            continue
        problem = check_schema(entry.tool.parameters)
        if problem is not None:
            invalid.append((name, problem))
            continue
        entries[name] = entry
    return Assembly(entries=entries, invalid=tuple(invalid))


def _refuse_conflicts(pack_tools: Sequence[PackTool], mcp: Sequence[tuple[str, Sequence[ToolSpec]]]) -> None:
    """Pack com o nome de um alias, ou o mesmo nome completo duas vezes: falha fechada, nunca escolher em silêncio."""
    packs = {tool.pack for tool in pack_tools}
    for alias, _specs in mcp:
        if alias in packs:
            raise CatalogConflict(alias)
    seen: set[str] = set()
    names = [tool.name for tool in pack_tools] + [f"{alias}.{spec.name}" for alias, specs in mcp for spec in specs]
    for name in names:
        if name in seen:
            raise CatalogConflict(name)
        seen.add(name)


def _collections_allowed(tool: PackTool, collections: frozenset[str]) -> bool:
    """Retriever só existe na execução se **todas** as coleções que declara estão no grant (clarificação 2)."""
    if tool.spec.kind != "retrieval":
        return True
    return tool.retriever is not None and tool.retriever.collections <= collections


def _from_pack(tool: PackTool) -> Entry:
    return Entry(
        tool=_catalog_tool(tool.name, tool.spec),
        pack=tool.pack,
        handler=tool.spec.handler,
        retriever=tool.retriever,
        local_name=tool.spec.name,
        trusted_schema=True,
    )


def _from_mcp(alias: str, spec: ToolSpec) -> Entry:
    return Entry(
        tool=_catalog_tool(f"{alias}.{spec.name}", spec),
        alias=alias,
        local_name=spec.name,
        trusted_schema=False,
    )


def _catalog_tool(name: str, spec: ToolSpec) -> CatalogTool:
    return CatalogTool(
        name=name, description=spec.description, parameters=spec.parameters, kind=spec.kind, mutates=spec.mutates
    )
