"""Formatos dos Assistants de sistema na administração (contracts/admin-api.md; 003 US10, ADR-032). Puro."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from axon_ai.assistants.api import (
    AuthOverride,
    McpOverride,
    ModelsOverride,
    OverrideHistoryEntry,
    OverridePayload,
    Scheme,
    SystemAssistantView,
)
from axon_ai.http.domain.admin_common import AdminInvalid, only, required, text, texts, version_of
from axon_ai.llm.api import MODEL_ROLES, ModelRef, ModelRole, ProviderStatus


def mcp_json(mcp: McpOverride) -> dict[str, Any]:
    return {"aliases": list(mcp.aliases), "allowed": sorted(mcp.allowed), "write": sorted(mcp.write)}


def auth_json(auth: AuthOverride) -> dict[str, Any]:
    """Esquemas ordenados; `allow` na ordem em que o admin os pôs (ADR-040)."""
    return {"schemes": sorted(auth.schemes), "allow": list(auth.allow)}


def models_json(roles: Mapping[ModelRole, ModelRef], vision: frozenset[ModelRole] = frozenset()) -> dict[str, Any]:
    """Papel → `provider/modelo`, ou `{model, vision: true}` no papel que enxerga imagem — a forma do YAML (ADR-044)."""
    return {
        role: {"model": str(ref), "vision": True} if role in vision else str(ref) for role, ref in sorted(roles.items())
    }


def provider_json(status: ProviderStatus) -> dict[str, Any]:
    """Um provider registrado e se está pronto (ADR-035): a console só oferece os prontos na escolha de modelo."""
    return {"name": status.name, "ready": status.ready, "detail": status.detail, "reports_cost": status.reports_cost}


def payload_json(payload: OverridePayload | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, ModelsOverride):
        return models_json(payload.roles, payload.vision)
    if isinstance(payload, AuthOverride):
        return auth_json(payload)
    return mcp_json(payload)


def view_json(view: SystemAssistantView) -> dict[str, Any]:
    return {
        "name": view.name,
        "description": view.description,
        "visibility": view.visibility,
        "flow": view.flow,
        "status": {"available": view.status.available, "reasons": list(view.status.reasons)},
        "overridable": sorted(view.overridable),
        "required_roles": list(view.required_roles),
        "allow": list(view.allow),
        "yaml": {
            "models": models_json(view.yaml_models, view.yaml_vision),
            "mcp": mcp_json(view.yaml_mcp),
            "auth": auth_json(view.yaml_auth),
        },
        "overrides": [
            {
                "section": override.section,
                "state": override.state,
                "reason": override.reason,
                "version": override.version,
                "updated_by": override.updated_by,
                "updated_at": override.updated_at.isoformat(),
                "payload": payload_json(override.payload),
            }
            for override in view.overrides
        ],
        "effective": {
            "models": models_json(view.effective_models, view.effective_vision),
            "mcp": mcp_json(view.effective_mcp),
            "auth": auth_json(view.effective_auth),
        },
    }


def history_json(entries: Sequence[OverrideHistoryEntry]) -> dict[str, Any]:
    return {
        "data": [
            {
                "section": entry.section,
                "action": entry.action,
                "payload": payload_json(entry.payload),
                "version": entry.version,
                "actor": entry.actor,
                "at": entry.at.isoformat(),
            }
            for entry in entries
        ]
    }


def _ref(value: object, field: str) -> ModelRef:
    if not isinstance(value, str):
        raise AdminInvalid(f"{field}: precisa ser 'provider/modelo'", field=field)
    try:
        return ModelRef.parse(value)
    except ValueError as error:
        raise AdminInvalid(f"{field}: {error}", field=field) from None


def _role(value: object, field: str) -> ModelRole:
    if value not in MODEL_ROLES:
        raise AdminInvalid(f"{field}: papel desconhecido; papéis: {', '.join(MODEL_ROLES)}", field=field)
    return value


def models_body(body: Mapping[str, Any]) -> tuple[ModelsOverride, int | None]:
    only(body, ("roles", "version"))
    roles = required(body, "roles")
    if not isinstance(roles, Mapping) or not roles:
        raise AdminInvalid("roles: precisa ser um objeto papel → modelo, com ao menos um papel", field="roles")
    parsed: dict[ModelRole, ModelRef] = {}
    vision: set[ModelRole] = set()
    for role, value in roles.items():
        field = f"roles.{role}"
        name = _role(role, field)
        if isinstance(value, Mapping):
            unknown = sorted(str(key) for key in value if key not in ("model", "vision"))
            if unknown:
                raise AdminInvalid(f"{field}.{unknown[0]}: campo desconhecido", field=f"{field}.{unknown[0]}")
            sees = value.get("vision", False)
            if not isinstance(sees, bool):
                raise AdminInvalid(f"{field}.vision: precisa ser true ou false", field=f"{field}.vision")
            parsed[name] = _ref(value.get("model"), f"{field}.model")
            if sees:
                vision.add(name)
        else:
            parsed[name] = _ref(value, field)
    return ModelsOverride(roles=parsed, vision=frozenset(vision)), version_of(body, nullable=True)


def mcp_body(body: Mapping[str, Any]) -> tuple[McpOverride, int | None]:
    only(body, ("aliases", "allowed", "write", "version"))
    aliases = texts(body, "aliases") or []
    allowed = texts(body, "allowed", optional=True) or []
    write = texts(body, "write", optional=True) or []
    return McpOverride(aliases=tuple(aliases), allowed=frozenset(allowed), write=frozenset(write)), version_of(
        body, nullable=True
    )


def auth_body(body: Mapping[str, Any]) -> tuple[AuthOverride, int | None]:
    """A seção `auth` inteira (ADR-040). Aqui, só a forma; o conteúdo — vazio, esquema desconhecido, seletor inválido,
    `*` em privado — é regra da 003, que devolve o campo (R58)."""
    only(body, ("schemes", "allow", "version"))
    schemes = texts(body, "schemes") or []
    allow = texts(body, "allow") or []
    override = AuthOverride(schemes=frozenset(cast("list[Scheme]", schemes)), allow=tuple(allow))
    return override, version_of(body, nullable=True)


def check_body(body: Mapping[str, Any]) -> tuple[ModelRole, ModelRef]:
    only(body, ("role", "model"))
    return _role(text(body, "role"), "role"), _ref(text(body, "model"), "model")


def version_param(raw: str | None) -> int:
    if raw is None or not raw.isdigit():
        raise AdminInvalid("version: obrigatória na query, inteiro não negativo", field="version")
    return int(raw)
