"""Tools remotas → `ToolSpec` pela allowlist do servidor (FR-007, US5; research R9). Puro.

O nome é o **local**, como o servidor o anuncia: o namespace `<alias>.<tool>` é aplicado pelo catálogo (004).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from axon_ai.mcp.api import SecurityPolicy
from axon_ai.mcp.domain.records import RemoteTool
from axon_ai_contracts import ToolSpec


def allowed_specs(remote: Sequence[RemoteTool], policy: SecurityPolicy) -> tuple[ToolSpec, ...]:
    """Só as tools anunciadas **e** na allowlist, na ordem em que o servidor as anuncia, com a marca de escrita."""
    allowed = set(policy.allowed_tools)
    write = set(policy.write_tools)
    specs: list[ToolSpec] = []
    seen: set[str] = set()
    for tool in remote:
        if tool.name not in allowed or tool.name in seen:
            continue
        seen.add(tool.name)
        specs.append(
            ToolSpec(
                name=tool.name,
                description=(tool.description or "").strip() or tool.name,
                parameters=tool.input_schema if isinstance(tool.input_schema, Mapping) else {},
                kind="mcp",
                mutates=tool.name in write,
            )
        )
    return tuple(specs)


def missing_tools(remote: Sequence[RemoteTool], policy: SecurityPolicy) -> tuple[str, ...]:
    """Da allowlist, as que o servidor não anuncia — para a saúde (R14)."""
    announced = {tool.name for tool in remote}
    return tuple(name for name in policy.allowed_tools if name not in announced)
