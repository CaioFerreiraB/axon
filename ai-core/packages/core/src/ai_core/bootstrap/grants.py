"""Assistants de sistema e resolução de grant (specs/011-core-bootstrap/contracts/configuration.md).

Até a 003 existir, é aqui que a fronteira de isolamento é montada — a partir de **configuração**, nunca de código
(princípio IV). Quando a 003 chegar, ela assume o `assistants.yaml` e a composition root passa a consumir o seam dela
(research R4).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from ai_core.bootstrap.settings import ConfigurationError
from ai_core.graph.api import FLOW_CHAT
from ai_core.http.ports import AssistantNotFound, Principal
from ai_core.llm.api import ModelPolicy, ModelRef, ModelRole
from ai_core.packs.api import Composition, CompositionError, PackRegistry

GENERATION: Final[ModelRole] = "generation"
_ASSISTANT_KEYS: Final = frozenset({"flow", "packs", "models", "allow"})


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantConfig:
    """Um Assistant de sistema, como o operador o declarou."""

    name: str
    flow: str
    packs: tuple[str, ...]
    models: Mapping[ModelRole, ModelRef]
    allow: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfiguredGrant:
    """O grant da Fase 1. Cumpre o `Protocol` `ExecutionGrant` da 005 sem que este módulo o implemente por herança."""

    assistant: str
    flow: str
    composition: Composition
    models: ModelPolicy


def load_assistants(path: Path | None) -> dict[str, AssistantConfig]:
    """Lê o `assistants.yaml`. Ausência de arquivo é configuração válida: nenhum Assistant existe."""
    if path is None:
        return {}
    data = _read(path)
    if not isinstance(data, dict) or "assistants" not in data:
        raise ConfigurationError(f"{path}: a raiz precisa ser um mapeamento com a chave 'assistants'")
    raw = data["assistants"] or {}
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path}: 'assistants' precisa ser um mapeamento de nome → configuração")
    return {str(name): _assistant(path, str(name), body) for name, body in raw.items()}


def _read(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ConfigurationError(f"arquivo de assistants não encontrado: {path}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigurationError(f"{path}: YAML inválido: {error}") from error


def _assistant(path: Path, name: str, body: object) -> AssistantConfig:
    where = f"assistants.{name}"
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise ConfigurationError(f"{path}: {where} precisa ser um mapeamento")
    unknown = sorted(str(key) for key in body if key not in _ASSISTANT_KEYS)
    if unknown:
        raise ConfigurationError(f"{path}: {where}: chave desconhecida: {', '.join(unknown)}")

    models = body.get("models")
    if not isinstance(models, dict) or GENERATION not in models:
        raise ConfigurationError(f"{path}: {where}.models precisa declarar ao menos '{GENERATION}'")

    return AssistantConfig(
        name=name,
        flow=str(body.get("flow") or FLOW_CHAT),
        packs=tuple(str(pack) for pack in body.get("packs") or ()),
        models={role: _ref(path, where, str(role), str(value)) for role, value in models.items()},
        allow=tuple(str(pattern) for pattern in body.get("allow") or ()),
    )


def _ref(path: Path, where: str, role: str, value: str) -> ModelRef:
    try:
        return ModelRef.parse(value)
    except ValueError as error:
        raise ConfigurationError(f"{path}: {where}.models.{role}: {error}") from error


def validate_flows(assistants: Mapping[str, AssistantConfig], available: Collection[str]) -> None:
    """Flow inexistente é erro de configuração, não surpresa em tempo de execução (005 US5)."""
    known = ", ".join(sorted(available)) or "nenhum"
    for assistant in assistants.values():
        if assistant.flow not in available:
            raise ConfigurationError(
                f"assistants.{assistant.name}.flow: flow '{assistant.flow}' não existe; disponíveis: {known}"
            )


class ConfiguredGrants:
    """Resolvedor de grant da Fase 1: cumpre a porta `GrantResolver` da 008."""

    def __init__(self, assistants: Mapping[str, AssistantConfig], packs: PackRegistry) -> None:
        self._assistants = dict(assistants)
        self._packs = packs

    async def resolve(self, *, model: str, principal: Principal) -> ConfiguredGrant:
        """`<assistant>` ou `<assistant>/<modelo>`; a parte do modelo só restringe, nunca amplia (princípio IV)."""
        name, _, requested = model.partition("/")
        assistant = self._assistants.get(name)
        if assistant is None:
            raise AssistantNotFound(f"assistant '{name}' não existe ou não é visível")
        try:
            composition = self._packs.compose(assistant.packs)
        except CompositionError as error:
            raise AssistantNotFound(f"assistant '{name}' indisponível: {error}") from error
        return ConfiguredGrant(
            assistant=name,
            flow=assistant.flow,
            composition=composition,
            models=_policy(assistant, requested),
        )


def _policy(assistant: AssistantConfig, requested: str) -> ModelPolicy:
    """O modelo pedido troca só o papel `generation`; a allowlist do Assistant continua valendo."""
    roles: dict[ModelRole, ModelRef] = dict(assistant.models)
    if requested:
        roles[GENERATION] = ModelRef(provider=roles[GENERATION].provider, model=requested)
    return ModelPolicy(roles=roles, allow=assistant.allow)


def assistant_names(assistants: Mapping[str, AssistantConfig]) -> Sequence[str]:
    return sorted(assistants)
