"""Validação de referências (FR-011): o que torna um Assistant indisponível, com motivos que nomeiam campo e
referência. A mesma função serve à resolução, ao boot e ao `assistants validate`."""

from __future__ import annotations

from collections.abc import Collection, Sequence

from ai_core.assistants.api import AssistantStatus
from ai_core.assistants.domain.definitions import AssistantDefinition


def reference_reasons(
    definition: AssistantDefinition,
    *,
    flow: str | None,
    flows: Collection[str],
    composition_error: str | None,
    mcp_aliases: frozenset[str],
    collections: frozenset[str],
) -> tuple[str, ...]:
    """Problemas de carga mais referências pendentes. Vazio = disponível."""
    reasons = list(definition.problems)
    if flow is not None and flow not in flows:
        available = ", ".join(sorted(flows)) or "nenhum"
        reasons.append(f"flow: flow '{flow}' não existe; disponíveis: {available}")
    if composition_error is not None:
        reasons.append(f"packs: {composition_error}")
    for alias in definition.mcp:
        if alias not in mcp_aliases:
            # Mesma mensagem para inexistente e para MCP de outro usuário (US6 cen. 2).
            reasons.append(f"mcp: MCP '{alias}' não existe ou não é visível")
    for name in definition.collections:
        if name not in collections:
            reasons.append(f"collections: coleção '{name}' não existe")
    return tuple(reasons)


def status_of(definition: AssistantDefinition, reasons: Sequence[str]) -> AssistantStatus:
    return AssistantStatus(
        name=definition.name,
        origin=definition.origin,
        available=not reasons,
        reasons=tuple(reasons),
        owner=definition.owner,
    )
