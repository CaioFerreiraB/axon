"""Resolução por papel e allowlist: as políticas puras da 006 (princípio XIII — sem I/O, sem relógio, sem trace)."""

from __future__ import annotations

from collections.abc import Sequence
from fnmatch import fnmatchcase

from ai_core.llm.api import ModelNotAllowed, ModelPolicy, ModelRef, ModelRole, RoleNotConfigured


def resolve(policy: ModelPolicy, role: ModelRole) -> ModelRef:
    """Modelo do papel. Papel não declarado é erro explícito — o roteador nunca escolhe sozinho (FR-002)."""
    try:
        return policy.roles[role]
    except KeyError:
        configured = ", ".join(policy.configured_roles()) or "nenhum"
        raise RoleNotConfigured(f"papel '{role}' não configurado; papéis configurados: {configured}") from None


def is_allowed(ref: ModelRef, patterns: Sequence[str]) -> bool:
    """Casa `provider/modelo` contra os padrões da allowlist. Lista vazia = nenhuma restrição declarada (R9)."""
    if not patterns:
        return True
    text = str(ref)
    return any(fnmatchcase(text, pattern) for pattern in patterns)


def ensure_allowed(ref: ModelRef, patterns: Sequence[str]) -> ModelRef:
    """Devolve a referência ou levanta `ModelNotAllowed` nomeando referência e padrões (FR-003)."""
    if not is_allowed(ref, patterns):
        allowed = ", ".join(patterns)
        raise ModelNotAllowed(f"modelo não permitido: {ref}; allowlist: {allowed}")
    return ref
