"""JSON ⇄ rascunho de Assistant de usuário (US4, research R19). Só o mapeamento: as regras são da 003.

O corpo espelha o `UserAssistantDraft`, com modelos em texto `provider/modelo` — o mesmo do `assistants.yaml`.
Visibilidade, esquemas e ACL não são campos (003 FR-012): enviá-los é recusado como campo desconhecido.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from axon_ai.assistants.api import DraftLimits, UserAssistant, UserAssistantDraft
from axon_ai.http.domain.errors import InvalidRequest
from axon_ai.llm.api import ModelRef, ModelRole

DRAFT_FIELDS: Final = frozenset(
    {"name", "description", "flow", "packs", "mcp", "collections", "models", "limits", "allowed_tools", "write_tools"}
)
LIMIT_FIELDS: Final = ("rpm", "max_iterations", "max_context_tokens")


def draft_from_json(body: Mapping[str, Any], *, name: str | None = None) -> UserAssistantDraft:
    """Rascunho a partir do corpo. `name`, se dado (o nome do caminho), preenche o corpo que não o traz."""
    for key in sorted(str(k) for k in body if k not in DRAFT_FIELDS):
        raise InvalidRequest(f"campo '{key}' não é aceito num Assistant de usuário", field=key)
    fields = dict(body)
    if name is not None and "name" not in fields:
        fields["name"] = name.removeprefix("~")
    raw_name = fields.get("name")
    if not isinstance(raw_name, str):
        raise InvalidRequest("campo 'name' é obrigatório", field="name")

    allowed = fields.get("allowed_tools")
    models, vision = _models(fields.get("models"))
    return UserAssistantDraft(
        name=raw_name,
        description=_optional_text(fields, "description"),
        flow=_optional_text(fields, "flow"),
        packs=_texts(fields, "packs"),
        mcp=_texts(fields, "mcp"),
        collections=_texts(fields, "collections"),
        models=models,
        vision=vision,
        limits=_limits(fields.get("limits")),
        allowed_tools=None if allowed is None else _texts(fields, "allowed_tools"),
        write_tools=_texts(fields, "write_tools"),
    )


def draft_json(draft: UserAssistantDraft) -> dict[str, Any]:
    return {
        "name": draft.name,
        "description": draft.description,
        "flow": draft.flow,
        "packs": list(draft.packs),
        "mcp": list(draft.mcp),
        "collections": list(draft.collections),
        "models": {
            role: {"model": str(ref), "vision": True} if role in draft.vision else str(ref)
            for role, ref in draft.models.items()
        },
        "limits": {name: getattr(draft.limits, name) for name in LIMIT_FIELDS},
        "allowed_tools": list(draft.allowed_tools) if draft.allowed_tools is not None else None,
        "write_tools": list(draft.write_tools),
    }


def user_assistant_json(assistant: UserAssistant) -> dict[str, Any]:
    return {
        "name": assistant.name,
        "owner": assistant.owner,
        "created_at": assistant.created_at.isoformat(),
        "updated_at": assistant.updated_at.isoformat(),
        "status": {"available": assistant.status.available, "reasons": list(assistant.status.reasons)},
        "draft": draft_json(assistant.draft),
    }


def _optional_text(fields: Mapping[str, Any], key: str) -> str | None:
    value = fields.get(key)
    if value is not None and not isinstance(value, str):
        raise InvalidRequest(f"campo '{key}' precisa ser um texto", field=key)
    return value


def _texts(fields: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = fields.get(key)
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise InvalidRequest(f"campo '{key}' precisa ser uma lista de textos", field=key)
    if not all(isinstance(item, str) for item in value):
        raise InvalidRequest(f"campo '{key}' precisa ser uma lista de textos", field=key)
    return tuple(value)


def _models(value: Any) -> tuple[dict[ModelRole, ModelRef], frozenset[ModelRole]]:
    """Papel → `provider/modelo`, ou `{model, vision}` no papel que enxerga imagem (ADR-044, item 10)."""
    if not isinstance(value, Mapping):
        raise InvalidRequest("campo 'models' precisa ser um objeto papel → 'provider/modelo'", field="models")
    models: dict[ModelRole, ModelRef] = {}
    vision: set[ModelRole] = set()
    for role, item in value.items():
        name = cast("ModelRole", str(role))
        ref = item
        if isinstance(item, Mapping):
            unknown = sorted(str(key) for key in item if key not in ("model", "vision"))
            if unknown:
                raise InvalidRequest(f"chave desconhecida em models.{role}: '{unknown[0]}'", field=f"models.{role}")
            sees = item.get("vision", False)
            if not isinstance(sees, bool):
                raise InvalidRequest(f"models.{role}.vision precisa ser booleano", field=f"models.{role}.vision")
            if sees:
                vision.add(name)
            ref = item.get("model")
        try:
            models[name] = ModelRef.parse(str(ref))
        except ValueError as error:
            raise InvalidRequest(str(error), field=f"models.{role}") from None
    return models, frozenset(vision)


def _limits(value: Any) -> DraftLimits:
    if value is None:
        return DraftLimits()
    if not isinstance(value, Mapping):
        raise InvalidRequest("campo 'limits' precisa ser um objeto", field="limits")
    for key in sorted(str(k) for k in value if k not in LIMIT_FIELDS):
        raise InvalidRequest(f"limite desconhecido: '{key}'", field=f"limits.{key}")
    for key in LIMIT_FIELDS:
        item = value.get(key)
        if item is not None and (isinstance(item, bool) or not isinstance(item, int)):
            raise InvalidRequest(f"limits.{key} precisa ser um inteiro", field=f"limits.{key}")
    return DraftLimits(**{key: value.get(key) for key in LIMIT_FIELDS})
