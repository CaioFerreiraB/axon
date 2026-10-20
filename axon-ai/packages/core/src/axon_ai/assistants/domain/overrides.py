"""Sobreposições de Assistants de sistema (ADR-032; research R28, R29): impressão digital da seção, estado de cada
sobreposição e a definição efetiva.

Puro: o armazenamento e o catálogo de tools dos packs chegam como dados. O deploy sempre vence — a sobreposição só vale
enquanto a seção está em `overrides` no YAML **e** a seção do YAML é a mesma de quando ela foi gravada; fora disso,
fica inativa, guardada e visível com o motivo.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast

from axon_ai.assistants.api import (
    McpOverride,
    ModelsOverride,
    OverrideAction,
    OverrideSection,
    OverrideState,
)
from axon_ai.assistants.domain.definitions import AssistantDefinition, allowed_model
from axon_ai.llm.api import MODEL_ROLES, ModelRef, ModelRole

NOT_ALLOWED: Final = "o deploy não permite mais"
SECTION_CHANGED: Final = "o deploy mudou a seção"
UNREADABLE: Final = "sobreposição ilegível"

type PackTools = Mapping[str, frozenset[str]]


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredOverride:
    """Uma sobreposição como o armazenamento a guarda: o conteúdo em JSON e a impressão digital da seção do YAML."""

    assistant: str
    section: OverrideSection
    payload: Mapping[str, object]
    fingerprint: str
    version: int
    updated_by: str
    updated_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class OverrideHistoryRecord:
    """Uma linha do histórico: gravação ou descarte, com o conteúdo gravado (FR-021)."""

    assistant: str
    section: OverrideSection
    action: OverrideAction
    payload: Mapping[str, object] | None
    version: int
    actor: str
    at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class OverrideStatus:
    """O estado de uma sobreposição guardada contra a definição atual do YAML."""

    stored: StoredOverride
    payload: ModelsOverride | McpOverride | None
    state: OverrideState
    reason: str | None = None


# --- seções do YAML ---------------------------------------------------------------------------------------------------


def yaml_mcp(definition: AssistantDefinition) -> McpOverride:
    """A seção `mcp` do YAML: os aliases e as entradas com namespace MCP de `allowed_tools` e `write_tools`."""
    aliases = set(definition.mcp)

    def of_mcp(entries: Sequence[str]) -> frozenset[str]:
        return frozenset(entry for entry in entries if entry.partition(".")[0] in aliases)

    return McpOverride(
        aliases=definition.mcp, allowed=of_mcp(definition.allowed_tools or ()), write=of_mcp(definition.write_tools)
    )


def section_fingerprint(definition: AssistantDefinition, section: OverrideSection) -> str:
    """SHA-256 do JSON canônico da seção. Em `models`, só os papéis: a allowlist é o teto, não a seção (R28)."""
    data: object
    if section == "models":
        data = {role: str(ref) for role, ref in sorted(definition.roles.items())}
    else:
        mcp = yaml_mcp(definition)
        data = {"aliases": sorted(mcp.aliases), "allowed": sorted(mcp.allowed), "write": sorted(mcp.write)}
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- conteúdo ---------------------------------------------------------------------------------------------------------


def payload_of(override: ModelsOverride | McpOverride) -> dict[str, object]:
    if isinstance(override, ModelsOverride):
        return {"roles": {role: str(ref) for role, ref in sorted(override.roles.items())}}
    return {"aliases": list(override.aliases), "allowed": sorted(override.allowed), "write": sorted(override.write)}


def read_payload(section: OverrideSection, payload: Mapping[str, object]) -> ModelsOverride | McpOverride | None:
    """O conteúdo guardado de volta em value object; `None` se ilegível (nunca aplicado em silêncio)."""
    try:
        if section == "models":
            roles = payload.get("roles")
            if not isinstance(roles, Mapping) or not all(role in MODEL_ROLES for role in roles):
                return None
            return ModelsOverride(
                roles={cast("ModelRole", role): ModelRef.parse(str(ref)) for role, ref in roles.items()}
            )
        aliases, allowed, write = payload.get("aliases"), payload.get("allowed"), payload.get("write")
        if not all(isinstance(value, list) for value in (aliases, allowed, write)):
            return None
        return McpOverride(
            aliases=tuple(map(str, cast("list[object]", aliases))),
            allowed=frozenset(map(str, cast("list[object]", allowed))),
            write=frozenset(map(str, cast("list[object]", write))),
        )
    except ValueError:
        return None


# --- estado e definição efetiva ---------------------------------------------------------------------------------------


def status_of_override(definition: AssistantDefinition, stored: StoredOverride) -> OverrideStatus:
    payload = read_payload(stored.section, stored.payload)
    if stored.section not in definition.overrides:
        return OverrideStatus(stored=stored, payload=payload, state="inactive", reason=NOT_ALLOWED)
    if stored.fingerprint != section_fingerprint(definition, stored.section):
        return OverrideStatus(stored=stored, payload=payload, state="inactive", reason=SECTION_CHANGED)
    return OverrideStatus(stored=stored, payload=payload, state="active")


def apply_models(definition: AssistantDefinition, override: ModelsOverride) -> AssistantDefinition:
    """Substitui os papéis. Modelo fora da allowlist do YAML (que pode ter mudado) vira problema `override.models`."""
    problems = tuple(
        f"override.models: models.{role}: {ref} fora da allowlist ({', '.join(definition.allow)})"
        for role, ref in sorted(override.roles.items())
        if not allowed_model(ref, definition.allow)
    )
    return dataclasses.replace(definition, roles=override.roles, problems=(*definition.problems, *problems))


def apply_mcp(definition: AssistantDefinition, override: McpOverride, *, pack_tools: PackTools) -> AssistantDefinition:
    """Troca os aliases e as entradas de MCP; as de pack ficam. Sem `allowed_tools` no YAML (tudo permitido) e com a
    sobreposição restringindo MCP, a lista efetiva enumera as tools dos packs mais as de MCP escolhidas (R29)."""
    yaml_aliases = set(definition.mcp)

    def of_packs(entries: Sequence[str]) -> tuple[str, ...]:
        return tuple(entry for entry in entries if entry.partition(".")[0] not in yaml_aliases)

    allowed: tuple[str, ...] | None
    if definition.allowed_tools is not None:
        allowed = (*of_packs(definition.allowed_tools), *sorted(override.allowed))
    elif override.allowed:
        packs = tuple(f"{pack}.{tool}" for pack in definition.packs for tool in sorted(pack_tools.get(pack, ())))
        allowed = (*packs, *sorted(override.allowed))
    else:
        allowed = None
    write = (*of_packs(definition.write_tools), *sorted(override.write))
    return dataclasses.replace(definition, mcp=override.aliases, allowed_tools=allowed, write_tools=write)


def effective(
    definition: AssistantDefinition, stored: Sequence[StoredOverride], *, pack_tools: PackTools
) -> tuple[AssistantDefinition, tuple[OverrideStatus, ...]]:
    """A definição que a resolução, a descoberta e a validação usam: o YAML mais as sobreposições ativas."""
    statuses = tuple(status_of_override(definition, record) for record in sorted(stored, key=lambda r: r.section))
    result = definition
    for status in statuses:
        if status.state != "active":
            continue
        if status.payload is None:
            problem = f"override.{status.stored.section}: {UNREADABLE}"
            result = dataclasses.replace(result, problems=(*result.problems, problem))
        elif isinstance(status.payload, ModelsOverride):
            result = apply_models(result, status.payload)
        else:
            result = apply_mcp(result, status.payload, pack_tools=pack_tools)
        result = dataclasses.replace(result, overridden=result.overridden | {status.stored.section})
    return result, statuses


_SECTION_FIELDS: Final[Mapping[OverrideSection, tuple[str, ...]]] = {
    "models": ("models",),
    "mcp": ("mcp", "allowed_tools", "write_tools"),
}


def attribute(reasons: Sequence[str], active: frozenset[OverrideSection]) -> tuple[str, ...]:
    """Motivo de indisponibilidade num campo sobreposto passa a nomear a sobreposição (`override.mcp: …`, R31): quem
    lê sabe que foi a administração, e não o YAML, que deixou o Assistant indisponível."""
    attributed: list[str] = []
    for reason in reasons:
        field = reason.partition(":")[0].partition(".")[0]
        section = next((s for s in active if field in _SECTION_FIELDS[s]), None)
        attributed.append(f"override.{section}: {reason}" if section and not reason.startswith("override.") else reason)
    return tuple(attributed)
