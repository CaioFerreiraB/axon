"""Políticas de Assistants de usuário (FR-014, research R10): primeira que casa e conformidade do rascunho.

Um Assistant de usuário é sempre privado, aceita os dois esquemas e tem o dono como único permitido (FR-012); sua
allowlist de modelos **é** a da política, e limite ausente assume o teto. A conformidade é conferida na criação, na
atualização e em cada resolução — na resolução, contra a política aplicável naquele momento.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from axon_ai.assistants.api import SCHEMES, USER_PREFIX, Limits, PolicyViolation, Principal, UserAssistantDraft
from axon_ai.assistants.domain.access import selector_matches
from axon_ai.assistants.domain.definitions import (
    AccessRule,
    AssistantDefinition,
    UserAssistantPolicy,
    allowed_model,
)
from axon_ai.assistants.domain.resolution import effective_flow


def applicable_policy(policies: Sequence[UserAssistantPolicy], principal: Principal) -> UserAssistantPolicy | None:
    """A primeira, na ordem declarada, cujo seletor casa. Unir políticas daria o que nenhuma concede sozinha."""
    for policy in policies:
        if selector_matches(policy.match, principal):
            return policy
    return None


def user_definition(
    draft: UserAssistantDraft,
    *,
    owner: str,
    allow: tuple[str, ...],
    limits: Limits,
    problems: tuple[str, ...] = (),
) -> AssistantDefinition:
    """A forma normalizada de um Assistant de usuário. Visibilidade, esquemas e ACL são fixos, não do rascunho."""
    return AssistantDefinition(
        name=f"{USER_PREFIX}{draft.name}",
        origin="user",
        owner=owner,
        description=draft.description,
        visibility="private",
        access=AccessRule(schemes=frozenset(SCHEMES), allow=(owner,)),
        flow=draft.flow,
        packs=draft.packs,
        mcp=draft.mcp,
        collections=draft.collections,
        allowed_tools=draft.allowed_tools,
        write_tools=draft.write_tools,
        roles=draft.models,
        allow=allow,
        limits=limits,
        problems=problems,
    )


def conform(
    draft: UserAssistantDraft,
    policy: UserAssistantPolicy,
    *,
    owner: str,
    mcp_aliases: frozenset[str],
    preferred: Callable[[str], str | None],
) -> AssistantDefinition:
    """A definição do rascunho sob a política, ou `PolicyViolation` nomeando o primeiro campo fora dela."""
    for pack in draft.packs:
        if pack not in policy.packs:
            raise PolicyViolation(f"pack '{pack}' não é permitido pela sua política", field="packs")

    flow = effective_flow(user_definition(draft, owner=owner, allow=(), limits=policy.limits), preferred)
    if flow is None:
        raise PolicyViolation("flow obrigatório em composição de dois ou mais packs", field="flow")
    if flow not in policy.flows:
        raise PolicyViolation(f"flow '{flow}' não é permitido pela sua política", field="flow")

    for collection in draft.collections:
        if collection not in policy.collections:
            raise PolicyViolation(f"coleção '{collection}' não é permitida pela sua política", field="collections")
    for alias in draft.mcp:
        if alias not in mcp_aliases:
            # Mesma mensagem para inexistente e para MCP de outro usuário (US6 cen. 2).
            raise PolicyViolation(f"MCP '{alias}' não existe ou não é visível", field="mcp")
    for role, ref in draft.models.items():
        if not allowed_model(ref, policy.models_allow):
            allowlist = ", ".join(policy.models_allow)
            raise PolicyViolation(f"{ref} fora da allowlist da sua política ({allowlist})", field=f"models.{role}")

    effective: dict[str, int | None] = {}
    for name in ("rpm", "max_iterations", "max_context_tokens"):
        value, ceiling = getattr(draft.limits, name), getattr(policy.limits, name)
        if value is not None and ceiling is not None and value > ceiling:
            raise PolicyViolation(f"{name} {value} acima do teto da sua política ({ceiling})", field=f"limits.{name}")
        effective[name] = value if value is not None else ceiling

    if draft.write_tools and not policy.write_tools:
        raise PolicyViolation("a sua política não permite tools de escrita", field="write_tools")

    return user_definition(
        draft,
        owner=owner,
        allow=policy.models_allow,
        limits=Limits(
            rpm=effective["rpm"] or policy.limits.rpm,
            max_iterations=effective["max_iterations"],
            max_context_tokens=effective["max_context_tokens"],
        ),
    )
