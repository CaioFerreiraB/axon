"""Definições de Assistant e políticas de usuário (contracts/assistants-yaml.md, data-model.md).

`AssistantDefinition` é a forma normalizada comum aos Assistants de sistema e de usuário: a resolução, a descoberta e a
validação só enxergam ela. Erro de **um** Assistant fica em `problems`, e só ele fica indisponível (princípio VII).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from types import MappingProxyType
from typing import Final, Literal, cast

from ai_core.assistants.api import (
    DEFAULT_RPM,
    DESCRIPTION_MAX,
    NAME_PATTERN,
    SCHEMES,
    SUBJECT_PATTERN,
    USER_PREFIX,
    AssistantsConfigError,
    Limits,
    Origin,
    Principal,
    Scheme,
)
from ai_core.assistants.domain.access import selector_matches
from ai_core.llm.api import MODEL_ROLES, ModelRef, ModelRole

type Visibility = Literal["public", "private"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessRule:
    """ACL de um Assistant: esquemas aceitos e seletores permitidos (`*`, `user:…`, `svc:…`, `group:…`)."""

    schemes: frozenset[Scheme] = frozenset()
    allow: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "schemes", frozenset(self.schemes))
        object.__setattr__(self, "allow", tuple(self.allow))

    def permits(self, principal: Principal) -> bool:
        """Esquema aceito **e** algum seletor casa. Regra vazia não permite ninguém (falha fechada)."""
        return principal.scheme in self.schemes and any(
            selector_matches(selector, principal) for selector in self.allow
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantDefinition:
    """Um Assistant como a plataforma o enxerga. Os defaults são os de falha fechada: sem ACL, ninguém entra."""

    name: str
    origin: Origin
    owner: str | None = None
    description: str | None = None
    visibility: Visibility = "private"
    access: AccessRule = field(default_factory=AccessRule)
    flow: str | None = None
    packs: tuple[str, ...] = ()
    mcp: tuple[str, ...] = ()
    collections: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] | None = None
    write_tools: tuple[str, ...] = ()
    roles: Mapping[ModelRole, ModelRef] = field(default_factory=lambda: MappingProxyType({}))
    allow: tuple[str, ...] = ()
    limits: Limits = field(default_factory=Limits)
    problems: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", MappingProxyType(dict(self.roles)))
        for name in ("packs", "mcp", "collections", "write_tools", "allow", "problems"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.allowed_tools is not None:
            object.__setattr__(self, "allowed_tools", tuple(self.allowed_tools))


@dataclass(frozen=True, slots=True, kw_only=True)
class UserAssistantPolicy:
    """Política do operador para Assistants de usuário (FR-014). `limits` são tetos."""

    match: str
    packs: frozenset[str] = frozenset()
    flows: frozenset[str] = frozenset()
    collections: frozenset[str] = frozenset()
    models_allow: tuple[str, ...]
    limits: Limits
    write_tools: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "packs", frozenset(self.packs))
        object.__setattr__(self, "flows", frozenset(self.flows))
        object.__setattr__(self, "collections", frozenset(self.collections))
        object.__setattr__(self, "models_allow", tuple(self.models_allow))


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantsConfig:
    """Tudo o que o operador declarou: Assistants de sistema, políticas de usuário e o grupo de administração."""

    assistants: Mapping[str, AssistantDefinition] = field(default_factory=lambda: MappingProxyType({}))
    policies: tuple[UserAssistantPolicy, ...] = ()
    admin_group: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "assistants", MappingProxyType(dict(self.assistants)))
        object.__setattr__(self, "policies", tuple(self.policies))


# ---------------------------------------------------------------------------------------------------------------------
# Leitura do `assistants.yaml` (contracts/assistants-yaml.md)
# ---------------------------------------------------------------------------------------------------------------------

PHASE1_ALLOW_MESSAGE: Final = (
    "`allow` saiu da raiz do Assistant: a allowlist de modelos vive em `models.allow`, e quem pode usar o "
    "Assistant, em `auth.allow`"
)
"""A chave antiga é recusada, não aceita como apelido: confundir as duas listas amplia acesso (research R3)."""

_TOP_KEYS: Final = frozenset({"assistants", "user_assistants", "api_keys"})
_ASSISTANT_KEYS: Final = frozenset(
    {
        "description",
        "visibility",
        "auth",
        "flow",
        "packs",
        "mcp",
        "collections",
        "allowed_tools",
        "write_tools",
        "models",
        "limits",
    }
)
_POLICY_KEYS: Final = frozenset({"match", "packs", "flows", "collections", "models", "limits", "write_tools"})
_LIMIT_KEYS: Final = ("rpm", "max_iterations", "max_context_tokens")
_VISIBILITIES: Final = ("public", "private")
_GROUP_PATTERN: Final = re.compile(r"group:\S+")


def allowed_model(ref: ModelRef, patterns: Sequence[str]) -> bool:
    """`provider/modelo` casa algum padrão da allowlist — a mesma regra da 006 (research R5)."""
    text = str(ref)
    return any(fnmatchcase(text, pattern) for pattern in patterns)


def is_selector(text: str) -> bool:
    """`*`, `user:…`, `svc:…` ou `group:…`."""
    return text == "*" or bool(SUBJECT_PATTERN.fullmatch(text)) or bool(_GROUP_PATTERN.fullmatch(text))


def read_config(data: object, *, origin: str) -> AssistantsConfig:
    """Interpreta o conteúdo já carregado do arquivo. Erro de arquivo levanta; erro de um Assistant vai para
    `problems` dele. `origin` (o caminho do arquivo) entra em toda mensagem de erro de arquivo."""
    if data is None:
        return AssistantsConfig()
    if not isinstance(data, Mapping):
        raise AssistantsConfigError(f"{origin}: a raiz precisa ser um mapeamento")
    unknown = sorted(str(key) for key in data if key not in _TOP_KEYS)
    if unknown:
        raise AssistantsConfigError(f"{origin}: chave de topo desconhecida: {', '.join(unknown)}")

    raw_assistants = data.get("assistants") or {}
    if not isinstance(raw_assistants, Mapping):
        raise AssistantsConfigError(f"{origin}: assistants precisa ser um mapeamento de nome → Assistant")

    return AssistantsConfig(
        assistants={str(name): _system_assistant(str(name), body) for name, body in raw_assistants.items()},
        policies=_policies(origin, data.get("user_assistants")),
        admin_group=_admin_group(origin, data.get("api_keys")),
    )


class _Problems:
    """Acumula os problemas de um Assistant: cada um nomeia o campo."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, field_name: str, message: str) -> None:
        self.items.append(f"{field_name}: {message}")


def _system_assistant(name: str, body: object) -> AssistantDefinition:
    problems = _Problems()
    if name.startswith(USER_PREFIX):
        problems.add("nome", f"começa com '{USER_PREFIX}', reservado aos Assistants de usuário (FR-017)")
    elif not NAME_PATTERN.fullmatch(name):
        problems.add("nome", f"fora do formato {NAME_PATTERN.pattern}")

    if body is None:
        body = {}
    if not isinstance(body, Mapping):
        problems.add("assistant", "precisa ser um mapeamento")
        return AssistantDefinition(name=name, origin="system", problems=tuple(problems.items))

    if "allow" in body:
        problems.items.append(PHASE1_ALLOW_MESSAGE)
    for key in sorted(str(k) for k in body if k not in _ASSISTANT_KEYS and k != "allow"):
        problems.add(key, "chave desconhecida")

    description = body.get("description")
    if description is not None and (not isinstance(description, str) or len(description) > DESCRIPTION_MAX):
        problems.add("description", f"precisa ser um texto de até {DESCRIPTION_MAX} caracteres")
        description = None

    visibility: Visibility = "private"
    raw_visibility = body.get("visibility")
    if raw_visibility in _VISIBILITIES:
        visibility = cast("Visibility", raw_visibility)
    else:
        problems.add("visibility", f"obrigatória, '{_VISIBILITIES[0]}' ou '{_VISIBILITIES[1]}'")

    access = _access(body.get("auth"), problems)
    if visibility == "private" and "*" in access.allow:
        problems.add("auth.allow", "'*' não é permitido em Assistant privado: nomeie subjects ou grupos (FR-012)")

    packs = _texts(body, "packs", problems)
    write_tools = _texts(body, "write_tools", problems)
    if visibility == "public" and write_tools:
        problems.add("write_tools", "Assistant público nunca concede tools de escrita (FR-012)")

    flow = body.get("flow")
    if flow is not None and (not isinstance(flow, str) or not flow.strip()):
        problems.add("flow", "precisa ser um nome de flow")
        flow = None
    if flow is None and len(packs) >= 2:
        problems.add("flow", "obrigatório em composição de dois ou mais packs: o flow é escolhido pelo Assistant")

    roles, allow = _models(body.get("models"), problems)
    allowed_tools = _texts(body, "allowed_tools", problems) if "allowed_tools" in body else None

    return AssistantDefinition(
        name=name,
        origin="system",
        description=description,
        visibility=visibility,
        access=access,
        flow=flow,
        packs=packs,
        mcp=_texts(body, "mcp", problems),
        collections=_texts(body, "collections", problems),
        allowed_tools=allowed_tools,
        write_tools=write_tools,
        roles=roles,
        allow=allow,
        limits=_limits(body.get("limits"), problems),
        problems=tuple(problems.items),
    )


def _texts(body: Mapping[str, object], key: str, problems: _Problems, *, label: str | None = None) -> tuple[str, ...]:
    where = label or key
    value = body.get(key)
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        problems.add(where, "precisa ser uma lista")
        return ()
    items = tuple(value)
    if not all(isinstance(item, str) and item.strip() for item in items):
        problems.add(where, "itens precisam ser textos não vazios")
        return ()
    return tuple(str(item) for item in items)


def _access(raw: object, problems: _Problems) -> AccessRule:
    if not isinstance(raw, Mapping):
        problems.add("auth", "obrigatório, com `schemes` e `allow`")
        return AccessRule()
    for key in sorted(str(k) for k in raw if k not in ("schemes", "allow")):
        problems.add(f"auth.{key}", "chave desconhecida")

    schemes = _texts(raw, "schemes", problems, label="auth.schemes")
    unknown = [scheme for scheme in schemes if scheme not in SCHEMES]
    if not schemes or unknown:
        problems.add(
            "auth.schemes",
            f"não vazio, entre {', '.join(SCHEMES)}" + (f"; recebido: {', '.join(unknown)}" if unknown else ""),
        )
        schemes = ()

    allow = _texts(raw, "allow", problems, label="auth.allow")
    invalid = [selector for selector in allow if not is_selector(selector)]
    if not allow or invalid:
        detail = f"; inválidos: {', '.join(invalid)}" if invalid else ""
        problems.add("auth.allow", f"não vazio, com '*', 'user:…', 'svc:…' ou 'group:…'{detail}")
        allow = ()
    return AccessRule(schemes=frozenset(cast("tuple[Scheme, ...]", schemes)), allow=allow)


def _models(raw: object, problems: _Problems) -> tuple[dict[ModelRole, ModelRef], tuple[str, ...]]:
    if not isinstance(raw, Mapping):
        problems.add("models", "obrigatório, com ao menos `generation` e `allow`")
        problems.add("models.allow", "obrigatória e não vazia")
        return {}, ()

    allow = _texts(raw, "allow", problems, label="models.allow") if "allow" in raw else ()
    if not allow:
        problems.add("models.allow", "obrigatória e não vazia")

    roles: dict[ModelRole, ModelRef] = {}
    for key, value in raw.items():
        if key == "allow":
            continue
        if key not in MODEL_ROLES:
            problems.add(f"models.{key}", f"papel desconhecido; papéis: {', '.join(MODEL_ROLES)}")
            continue
        try:
            ref = ModelRef.parse(str(value))
        except ValueError as error:
            problems.add(f"models.{key}", str(error))
            continue
        if allow and not allowed_model(ref, allow):
            problems.add(f"models.{key}", f"{ref} fora da allowlist ({', '.join(allow)})")
            continue
        roles[cast("ModelRole", key)] = ref
    if "generation" not in raw:
        problems.add("models.generation", "obrigatório")
    return roles, allow


def _limit_values(raw: Mapping[str, object], problems: _Problems | None, where: str) -> dict[str, int | None]:
    values: dict[str, int | None] = {}
    for key in _LIMIT_KEYS:
        value = raw.get(key)
        if value is None:
            values[key] = None
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            message = f"precisa ser um inteiro ≥ 1: {value!r}"
            if problems is None:
                raise AssistantsConfigError(f"{where}.{key}: {message}")
            problems.add(f"limits.{key}", message)
            values[key] = None
            continue
        values[key] = value
    return values


def _limits(raw: object, problems: _Problems) -> Limits:
    if raw is None:
        return Limits()
    if not isinstance(raw, Mapping):
        problems.add("limits", "precisa ser um mapeamento")
        return Limits()
    for key in sorted(str(k) for k in raw if k not in _LIMIT_KEYS):
        problems.add(f"limits.{key}", "chave desconhecida")
    values = _limit_values(raw, problems, "limits")
    return Limits(
        rpm=values["rpm"] or DEFAULT_RPM,
        max_iterations=values["max_iterations"],
        max_context_tokens=values["max_context_tokens"],
    )


def _policies(origin: str, raw: object) -> tuple[UserAssistantPolicy, ...]:
    """Política malformada para o boot: pular uma mudaria qual é a primeira que casa (contracts/assistants-yaml.md)."""
    if raw is None:
        return ()
    if not isinstance(raw, Mapping):
        raise AssistantsConfigError(f"{origin}: user_assistants precisa ser um mapeamento com `policies`")
    for key in raw:
        if key != "policies":
            raise AssistantsConfigError(f"{origin}: user_assistants.{key}: chave desconhecida")
    items = raw.get("policies") or []
    if isinstance(items, str) or not isinstance(items, Sequence):
        raise AssistantsConfigError(f"{origin}: user_assistants.policies precisa ser uma lista")
    return tuple(_policy(origin, f"user_assistants.policies[{index}]", item) for index, item in enumerate(items))


def _policy(origin: str, where: str, raw: object) -> UserAssistantPolicy:
    def fail(field_name: str, message: str) -> AssistantsConfigError:
        return AssistantsConfigError(f"{origin}: {where}.{field_name}: {message}")

    if not isinstance(raw, Mapping):
        raise AssistantsConfigError(f"{origin}: {where}: precisa ser um mapeamento")
    for key in raw:
        if key not in _POLICY_KEYS:
            raise fail(str(key), "chave desconhecida")

    match = raw.get("match")
    if not isinstance(match, str) or not (match == "*" or _GROUP_PATTERN.fullmatch(match)):
        raise fail("match", "obrigatório, '*' ou 'group:<nome>'")

    def names(key: str) -> frozenset[str]:
        problems = _Problems()
        values = _texts(raw, key, problems)
        if problems.items:
            raise fail(key, problems.items[0].split(": ", 1)[1])
        return frozenset(values)

    models = raw.get("models")
    if not isinstance(models, Mapping):
        raise fail("models.allow", "obrigatória e não vazia")
    for key in models:
        if key != "allow":
            raise fail(f"models.{key}", "chave desconhecida; a política só declara a allowlist")
    allow_problems = _Problems()
    allow = _texts(models, "allow", allow_problems)
    if allow_problems.items or not allow:
        raise fail("models.allow", "obrigatória e não vazia")

    limits = raw.get("limits")
    if not isinstance(limits, Mapping) or limits.get("rpm") is None:
        raise fail("limits.rpm", "obrigatório: é o teto de execuções por minuto")
    for key in limits:
        if key not in _LIMIT_KEYS:
            raise fail(f"limits.{key}", "chave desconhecida")
    values = _limit_values(limits, None, f"{origin}: {where}.limits")

    write_tools = raw.get("write_tools", False)
    if not isinstance(write_tools, bool):
        raise fail("write_tools", "precisa ser true ou false")

    return UserAssistantPolicy(
        match=match,
        packs=names("packs"),
        flows=names("flows"),
        collections=names("collections"),
        models_allow=allow,
        limits=Limits(
            rpm=cast("int", values["rpm"]),
            max_iterations=values["max_iterations"],
            max_context_tokens=values["max_context_tokens"],
        ),
        write_tools=write_tools,
    )


def _admin_group(origin: str, raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise AssistantsConfigError(f"{origin}: api_keys precisa ser um mapeamento")
    for key in raw:
        if key != "admin_group":
            raise AssistantsConfigError(f"{origin}: api_keys.{key}: chave desconhecida")
    group = raw.get("admin_group")
    if group is None:
        return None
    if not isinstance(group, str) or not group.removeprefix("group:").strip():
        raise AssistantsConfigError(f"{origin}: api_keys.admin_group: precisa ser um nome de grupo")
    return group.removeprefix("group:").strip()
