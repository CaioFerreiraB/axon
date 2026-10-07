"""Validação de referências (FR-011): o que torna um Assistant indisponível, com motivos que nomeiam campo e
referência. A mesma função serve à resolução, ao boot e ao `assistants validate`."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from ai_core.assistants.api import AssistantStatus
from ai_core.assistants.domain.definitions import AssistantDefinition
from ai_core.llm.api import ModelRole

type FlowRoles = Mapping[str, Sequence[ModelRole]]
"""Papéis de modelo exigidos por flow, publicados pelo motor (005, ADR-019)."""

type PackTools = Mapping[str, frozenset[str]]
"""Por pack, os nomes das tools nativas e dos retrievers que ele oferece (catálogo coletado na carga, 002)."""


def reference_reasons(
    definition: AssistantDefinition,
    *,
    flow: str | None,
    flows: Collection[str],
    composition_error: str | None,
    mcp_aliases: frozenset[str],
    collections: frozenset[str],
    flow_roles: FlowRoles | None = None,
    pack_tools: PackTools | None = None,
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
    reasons.extend(static_reasons(definition, flow=flow, flow_roles=flow_roles, pack_tools=pack_tools or {}))
    return tuple(reasons)


def static_reasons(
    definition: AssistantDefinition, *, flow: str | None, flow_roles: FlowRoles | None, pack_tools: PackTools
) -> tuple[str, ...]:
    """As regras da Fase 3 que não dependem de catálogo externo: papéis por flow, entradas de tool e colisão. São as
    que a criação e a atualização de um Assistant de usuário também aplicam (research R22)."""
    return (
        *role_reasons(definition, flow=flow, flow_roles=flow_roles),
        *tool_reasons(definition, pack_tools=pack_tools),
        *collision_reasons(definition),
    )


def role_reasons(definition: AssistantDefinition, *, flow: str | None, flow_roles: FlowRoles | None) -> tuple[str, ...]:
    """Papéis que o flow efetivo exige e o Assistant não declara (R19). A regra é do motor; aqui só se compara."""
    if flow is None or flow_roles is None:
        return ()
    return tuple(
        f"models: o flow '{flow}' exige o papel '{role}', que o Assistant não declara"
        for role in flow_roles.get(flow, ())
        if role not in definition.roles
    )


def tool_reasons(definition: AssistantDefinition, *, pack_tools: PackTools) -> tuple[str, ...]:
    """Entradas de `allowed_tools` e `write_tools` que nunca casariam no gateway (R20). Sem rede: tool de MCP é
    conferida só pelo alias; o namespace é o trecho antes do **primeiro** `.`."""
    reasons: list[str] = []
    for field, entries in (("allowed_tools", definition.allowed_tools or ()), ("write_tools", definition.write_tools)):
        for entry in entries:
            reason = _entry_reason(entry, definition, pack_tools)
            if reason is not None:
                reasons.append(f"{field}: {reason}")
    return tuple(reasons)


def _entry_reason(entry: str, definition: AssistantDefinition, pack_tools: PackTools) -> str | None:
    namespace, dot, tool = entry.partition(".")
    if not dot:
        return f"'{entry}' precisa de namespace: <pack>.<tool> ou <alias>.<tool>"
    if namespace in definition.mcp:
        return None
    if namespace not in definition.packs:
        return f"'{entry}': '{namespace}' não é pack nem MCP deste Assistant"
    offered = pack_tools.get(namespace)
    if offered is None or tool in offered:
        # Pack sem capacidades está em erro: o erro de composição já está nos motivos.
        return None
    return f"'{entry}': o pack '{namespace}' não oferece '{tool}'"


def collision_reasons(definition: AssistantDefinition) -> tuple[str, ...]:
    """Alias MCP com o nome de um pack do mesmo Assistant: `<nome>.<tool>` seria ambíguo no catálogo (R21)."""
    return tuple(
        f"mcp: o alias '{alias}' colide com o pack '{alias}': as tools '{alias}.<tool>' seriam ambíguas"
        for alias in definition.mcp
        if alias in definition.packs
    )


def status_of(definition: AssistantDefinition, reasons: Sequence[str]) -> AssistantStatus:
    return AssistantStatus(
        name=definition.name,
        origin=definition.origin,
        available=not reasons,
        reasons=tuple(reasons),
        owner=definition.owner,
    )
