"""Resolução: decomposição do id de modelo, regra do flow e montagem do grant (research R4, R5).

Funções puras: o que depende de I/O (composição de packs, catálogos, orçamento) chega por parâmetro, já calculado pelo
serviço.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ai_core.assistants.api import AssistantNotFound, ExecutionGrant, Principal, RequestRejected
from ai_core.assistants.domain.definitions import AssistantDefinition, allowed_model
from ai_core.graph.api import FLOW_CHAT
from ai_core.llm.api import ModelPolicy, ModelRef
from ai_core.packs.api import Composition


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelSelection:
    """O id pedido, decomposto: o Assistant e, se houver, a parte que restringe o modelo de geração."""

    assistant: str
    requested: str | None


def split_model_id(model: str) -> ModelSelection:
    """`<assistant>[/<resto>]`, dividindo no primeiro `/` — nome de Assistant nunca contém `/`."""
    name, separator, rest = model.partition("/")
    return ModelSelection(assistant=name, requested=rest if separator else None)


def not_found(name: str) -> AssistantNotFound:
    """A mesma mensagem para inexistente e para não autorizado: a existência de um privado não vaza (SC-001)."""
    return AssistantNotFound(f"assistant '{name}' não existe ou não é visível")


def effective_flow(definition: AssistantDefinition, preferred: Callable[[str], str | None]) -> str | None:
    """O flow declarado; sem declaração, o preferido do único pack, ou `chat` (US1 cen. 3).

    Composição sem flow devolve `None`: em composição o flow é escolhido pelo Assistant, não derivado (US1 cen. 4).
    """
    if definition.flow is not None:
        return definition.flow
    if len(definition.packs) >= 2:
        return None
    if len(definition.packs) == 1:
        return preferred(definition.packs[0]) or FLOW_CHAT
    return FLOW_CHAT


def select_models(definition: AssistantDefinition, requested: str | None) -> ModelPolicy:
    """A `ModelPolicy` da 006 (ADR-016): papéis e allowlist declarados, com o modelo pedido — se houver — no papel
    `generation`, e só dentro da allowlist (US4, FR-005).

    A parte pedida com `/` é `provider/modelo`; sem `/`, é um modelo do provider do `generation` declarado (a forma da
    Fase 1). Vazia, malformada ou fora da allowlist levanta `RequestRejected(field="model")` — antes de qualquer custo.
    """
    if requested is None:
        return ModelPolicy(roles=definition.roles, allow=definition.allow)
    try:
        if "/" in requested:
            ref = ModelRef.parse(requested)
        else:
            ref = ModelRef(provider=definition.roles["generation"].provider, model=requested)
    except ValueError as error:
        raise RequestRejected(f"modelo pedido inválido: {error}", field="model") from None
    if not allowed_model(ref, definition.allow):
        allowlist = ", ".join(definition.allow)
        raise RequestRejected(f"modelo não permitido: {ref}; allowlist: {allowlist}", field="model")
    roles = dict(definition.roles)
    roles["generation"] = ref
    return ModelPolicy(roles=roles, allow=definition.allow)


def build_grant(
    definition: AssistantDefinition,
    *,
    principal: Principal,
    flow: str,
    composition: Composition,
    models: ModelPolicy,
) -> ExecutionGrant:
    """Monta o grant só com o declarado. Público nunca leva tools de escrita, nem se o dado vier errado (FR-012)."""
    write_tools = () if definition.visibility == "public" else definition.write_tools
    return ExecutionGrant(
        assistant=definition.name,
        principal=principal,
        flow=flow,
        composition=composition,
        mcp_aliases=frozenset(definition.mcp),
        collections=frozenset(definition.collections),
        allowed_tools=frozenset(definition.allowed_tools) if definition.allowed_tools is not None else None,
        write_tools=frozenset(write_tools),
        models=models,
        limits=definition.limits,
    )
