"""Seams da spec 003: autenticação, resolução de grant, diretório de Assistants e administração de chaves.

Contrato em specs/003-core-assistants-access/contracts/assistants-api.md; campos e regras em data-model.md.

Único módulo da 003 que outros módulos importam. Depende só da stdlib e dos `api.py` de 002 (`Composition`) e 006
(`ModelPolicy`, `ModelRef`, `ModelRole` — só value objects, ADR-016). Não importa o resto do próprio módulo.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Final, Literal, Protocol

from axon_ai.llm.api import MODEL_ROLES, ModelPolicy, ModelRef, ModelRole
from axon_ai.packs.api import Composition

# ---------------------------------------------------------------------------------------------------------------------
# Vocabulário
# ---------------------------------------------------------------------------------------------------------------------

type Surface = Literal["public", "private", "admin"]
type Scheme = Literal["oidc", "api_key"]
type Origin = Literal["system", "user"]
type OverrideSection = Literal["models", "mcp", "auth"]
type OverrideState = Literal["active", "inactive"]
type OverrideAction = Literal["saved", "discarded"]

PUBLIC_SURFACE: Final = "public"
PRIVATE_SURFACE: Final = "private"
ADMIN_SURFACE: Final = "admin"
SCHEMES: Final[tuple[Scheme, ...]] = ("oidc", "api_key")
SCHEMES_OF_SURFACE: Final[Mapping[str, frozenset[Scheme]]] = MappingProxyType(
    {
        PUBLIC_SURFACE: frozenset({"oidc"}),
        PRIVATE_SURFACE: frozenset({"api_key"}),
        ADMIN_SURFACE: frozenset({"oidc", "api_key"}),
    }
)
"""A pública aceita só OIDC; a privada, só chave de API (FR-001); a de administração, os dois (ADR-031, research R25).
Na de administração, a credencial com o prefixo de chave segue o caminho de chave; qualquer outra, OIDC."""

SCHEME_OF_SURFACE: Final[Mapping[str, Scheme]] = MappingProxyType({PUBLIC_SURFACE: "oidc", PRIVATE_SURFACE: "api_key"})
"""**Depreciado** (ADR-031): o esquema único das duas superfícies antigas, derivado de `SCHEMES_OF_SURFACE`. Some na
série seguinte; use `SCHEMES_OF_SURFACE`."""

OVERRIDE_SECTIONS: Final[tuple[OverrideSection, ...]] = ("models", "mcp", "auth")
"""Seções de um Assistant de sistema que o YAML pode liberar para a administração (`overrides`, ADR-032)."""

USER_PREFIX: Final = "~"
"""Prefixo reservado dos Assistants de usuário (FR-017): nome de sistema nunca começa com ele."""

DEFAULT_RPM: Final = 60
"""Execuções por minuto quando o Assistant de sistema não declara: orçamento é controle de segurança (elo 7)."""

NAME_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
"""Nome de Assistant, sem o prefixo. Nunca contém `/`, que separa o Assistant do modelo no id pedido."""

SUBJECT_PATTERN: Final = re.compile(r"(user|svc):\S+")
"""Identificador de Principal: `user:<id>` ou `svc:<id>`."""

KEY_ID_PATTERN: Final = re.compile(r"[0-9a-f]{16}")
"""Parte pública de uma chave de API: 8 bytes em hexadecimal (research R7)."""

DESCRIPTION_MAX: Final = 500

WIDENING_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "packs",
        "mcp",
        "mcp_servers",
        "collections",
        "provider",
        "flow",
        "limits",
        "allowed_tools",
        "write_tools",
        "tools",
        "functions",
        "tool_choice",
        "function_call",
    }
)
"""Campos de requisição que ampliariam capacidade. A lista é daqui; quem os recusa no corpo é a borda (008, R13)."""


# ---------------------------------------------------------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------------------------------------------------------


class NotFound(LookupError):
    """Recurso inexistente **ou** não visível a quem pede. Um erro só para os dois casos, de propósito (FR-006)."""


class AssistantNotFound(NotFound):
    """Assistant inexistente ou ACL recusada — mesma mensagem, mesmo caminho (SC-001)."""


class AssistantUnavailable(RuntimeError):
    """Autorizado, mas indisponível: nunca resolvido com a referência ignorada (princípio VII)."""

    def __init__(self, message: str, *, reasons: Sequence[str]) -> None:
        super().__init__(message)
        self.reasons = tuple(reasons)


class RequestRejected(ValueError):
    """O pedido sai do permitido. `field` nomeia o campo, para que a borda o devolva ao cliente."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class PolicyViolation(RequestRejected):
    """Rascunho de Assistant de usuário fora da política aplicável (FR-014)."""


class NoApplicablePolicy(RequestRejected):
    """O Principal não casa com nenhuma política de Assistants de usuário (US6 cenário 6)."""


class Conflict(RuntimeError):
    """Criação com um nome que o próprio dono já usa, sobreposição gravada sobre uma versão desatualizada
    (`current_version` diz qual é a guardada; ADR-032) ou rotação de chave revogada, que não rotaciona (ADR-040)."""

    def __init__(self, message: str = "", *, current_version: int | None = None) -> None:
        super().__init__(message)
        self.current_version = current_version


class RateLimited(RuntimeError):
    """Orçamento do par (Principal, Assistant) esgotado na janela (US7). `retry_after` em segundos."""

    def __init__(self, message: str, *, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AssistantsConfigError(ValueError):
    """Erro de arquivo no `assistants.yaml`: o boot para. A mensagem nomeia o caminho do campo."""


# ---------------------------------------------------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------------------------------------------------


def _positive(name: str, value: int | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} precisa ser um inteiro ≥ 1: {value!r}")


@dataclass(frozen=True, slots=True, kw_only=True)
class Principal:
    """Quem pede. Avaliado a cada requisição; nada é guardado entre requisições."""

    subject: str
    scheme: Scheme
    groups: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not SUBJECT_PATTERN.fullmatch(self.subject):
            raise ValueError(f"subject precisa ser 'user:<id>' ou 'svc:<id>': {self.subject!r}")
        if self.scheme not in SCHEMES:
            raise ValueError(f"esquema desconhecido: {self.scheme!r}")
        object.__setattr__(self, "groups", frozenset(self.groups))


@dataclass(frozen=True, slots=True, kw_only=True)
class Limits:
    """Orçamento de uma execução. `None` = o default do motor (005)."""

    rpm: int = DEFAULT_RPM
    max_iterations: int | None = None
    max_context_tokens: int | None = None

    def __post_init__(self) -> None:
        _positive("rpm", self.rpm)
        _positive("max_iterations", self.max_iterations)
        _positive("max_context_tokens", self.max_context_tokens)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionGrant:
    """A configuração efetiva de uma execução: só o que o Assistant declara (FR-005, SC-002).

    Satisfaz estruturalmente o `ExecutionGrant` da 005 (`assistant`, `flow`, `composition`, `models`).
    """

    assistant: str
    principal: Principal
    flow: str
    composition: Composition
    mcp_aliases: frozenset[str] = frozenset()
    collections: frozenset[str] = frozenset()
    allowed_tools: frozenset[str] | None = None
    write_tools: frozenset[str] = frozenset()
    models: ModelPolicy
    limits: Limits

    def __post_init__(self) -> None:
        object.__setattr__(self, "mcp_aliases", frozenset(self.mcp_aliases))
        object.__setattr__(self, "collections", frozenset(self.collections))
        object.__setattr__(self, "write_tools", frozenset(self.write_tools))
        if self.allowed_tools is not None:
            object.__setattr__(self, "allowed_tools", frozenset(self.allowed_tools))

    @property
    def packs(self) -> tuple[str, ...]:
        """Packs na ordem declarada."""
        return self.composition.packs


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantSummary:
    """Item da descoberta: o que o Principal pode resolver (FR-008)."""

    name: str
    origin: Origin
    description: str | None
    generation: ModelRef
    allow: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class DraftLimits:
    """Limites pedidos por um Assistant de usuário; ausente = o teto da política."""

    rpm: int | None = None
    max_iterations: int | None = None
    max_context_tokens: int | None = None

    def __post_init__(self) -> None:
        for name in ("rpm", "max_iterations", "max_context_tokens"):
            try:
                _positive(name, getattr(self, name))
            except ValueError as error:
                raise RequestRejected(str(error), field=f"limits.{name}") from None


def _names(field_name: str, values: Collection[str]) -> tuple[str, ...]:
    items = tuple(values)
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise RequestRejected(f"{field_name}: itens precisam ser textos não vazios", field=field_name)
    return items


@dataclass(frozen=True, slots=True, kw_only=True)
class UserAssistantDraft:
    """O que o usuário envia ao criar ou atualizar um Assistant próprio. Guarda o nome **sem** o `~`.

    Visibilidade (privada), esquemas (os dois) e `allow` (só o dono) não são campos: são fixos (FR-012).
    """

    name: str
    description: str | None = None
    flow: str | None = None
    packs: tuple[str, ...] = ()
    mcp: tuple[str, ...] = ()
    collections: tuple[str, ...] = ()
    models: Mapping[ModelRole, ModelRef]
    vision: frozenset[ModelRole] = frozenset()
    """Papéis com `vision: true` (ADR-044, item 10); só papel de `models`."""
    limits: DraftLimits = field(default_factory=DraftLimits)
    allowed_tools: tuple[str, ...] | None = None
    write_tools: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        name = self.name.removeprefix(USER_PREFIX)
        if not NAME_PATTERN.fullmatch(name):
            raise RequestRejected(f"nome fora do formato {NAME_PATTERN.pattern}: {self.name!r}", field="name")
        object.__setattr__(self, "name", name)
        if self.description is not None and len(self.description) > DESCRIPTION_MAX:
            raise RequestRejected(f"description passa de {DESCRIPTION_MAX} caracteres", field="description")
        object.__setattr__(self, "packs", _names("packs", self.packs))
        object.__setattr__(self, "mcp", _names("mcp", self.mcp))
        object.__setattr__(self, "collections", _names("collections", self.collections))
        object.__setattr__(self, "write_tools", _names("write_tools", self.write_tools))
        if self.allowed_tools is not None:
            object.__setattr__(self, "allowed_tools", _names("allowed_tools", self.allowed_tools))
        unknown = sorted(str(role) for role in self.models if role not in MODEL_ROLES)
        if unknown:
            raise RequestRejected(f"papéis de modelo desconhecidos: {', '.join(unknown)}", field="models")
        if "generation" not in self.models:
            raise RequestRejected("models precisa declarar ao menos 'generation'", field="models.generation")
        object.__setattr__(self, "models", MappingProxyType(dict(self.models)))
        object.__setattr__(self, "vision", frozenset(self.vision))
        undeclared = sorted(str(role) for role in self.vision if role not in self.models)
        if undeclared:
            raise RequestRejected(f"vision em papel não declarado: {', '.join(undeclared)}", field="models")


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantStatus:
    """Estado de um Assistant na validação (FR-011). Cada motivo nomeia o campo e a referência."""

    name: str
    origin: Origin
    available: bool
    reasons: tuple[str, ...] = ()
    owner: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if self.available == bool(self.reasons):
            raise ValueError("disponível exige nenhum motivo; indisponível exige ao menos um")


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationReport:
    """Um estado por Assistant: de sistema primeiro, depois de usuário, cada grupo por nome."""

    statuses: tuple[AssistantStatus, ...]

    @property
    def ok(self) -> bool:
        return all(status.available for status in self.statuses)


@dataclass(frozen=True, slots=True, kw_only=True)
class UserAssistant:
    """Visão do dono. `status` é calculado na leitura, contra a política aplicável a quem lê."""

    name: str
    owner: str
    draft: UserAssistantDraft
    created_at: datetime
    updated_at: datetime
    status: AssistantStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiKeyInfo:
    """O que se pode mostrar de uma chave. Nunca a chave, nunca o hash (FR-015)."""

    key_id: str
    subject: str
    groups: frozenset[str] = frozenset()
    label: str | None = None
    created_at: datetime
    revoked_at: datetime | None = None
    rotated_at: datetime | None = None
    """Instante da última rotação do segredo (ADR-040); `key_id`, subject, grupos e rótulo não mudam nela."""

    def __post_init__(self) -> None:
        if not KEY_ID_PATTERN.fullmatch(self.key_id):
            raise ValueError(f"key_id fora do formato: {self.key_id!r}")
        if not SUBJECT_PATTERN.fullmatch(self.subject):
            raise ValueError(f"subject precisa ser 'user:<id>' ou 'svc:<id>': {self.subject!r}")
        object.__setattr__(self, "groups", frozenset(self.groups))

    @property
    def active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True, slots=True, kw_only=True)
class IssuedApiKey:
    """O único objeto que carrega a chave em claro — existe só na resposta da emissão."""

    info: ApiKeyInfo
    plaintext: str


# ---------------------------------------------------------------------------------------------------------------------
# Sobreposições de Assistants de sistema (Fase 9, ADR-032; data-model.md "Fase 9")
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelsOverride:
    """Os modelos por papel de um Assistant de sistema, cada um dentro da allowlist do YAML (que só muda por deploy)."""

    roles: Mapping[ModelRole, ModelRef]
    vision: frozenset[ModelRole] = frozenset()
    """Papéis com `vision: true` (ADR-044, item 10); a sobreposição de `models` é a seção inteira, `vision` incluso."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", MappingProxyType(dict(self.roles)))
        object.__setattr__(self, "vision", frozenset(self.vision))
        undeclared = sorted(str(role) for role in self.vision if role not in self.roles)
        if undeclared:
            raise ValueError(f"vision em papel não declarado: {', '.join(undeclared)}")


@dataclass(frozen=True, slots=True, kw_only=True)
class McpOverride:
    """Os servidores MCP e as tools de MCP permitidas e de escrita: entradas `<alias>.<tool>` de um alias daqui. As
    entradas de pack do YAML ficam como estão."""

    aliases: tuple[str, ...] = ()
    allowed: frozenset[str] = frozenset()
    write: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "aliases", tuple(dict.fromkeys(self.aliases)))
        object.__setattr__(self, "allowed", frozenset(self.allowed))
        object.__setattr__(self, "write", frozenset(self.write))


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthOverride:
    """Quem pode usar um Assistant de sistema: os esquemas aceitos e os seletores de `allow` (ADR-040). Não valida o
    conteúdo: a gravação o confere, e a configuração efetiva registra o que deixou de valer (research R41 a R43)."""

    schemes: frozenset[Scheme] = frozenset()
    allow: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "schemes", frozenset(self.schemes))
        object.__setattr__(self, "allow", tuple(dict.fromkeys(self.allow)))


type OverridePayload = ModelsOverride | McpOverride | AuthOverride


@dataclass(frozen=True, slots=True, kw_only=True)
class OverrideView:
    """Uma sobreposição guardada e o estado dela agora: inativa quando o deploy não a permite mais ou mudou a seção."""

    section: OverrideSection
    payload: OverridePayload
    state: OverrideState
    reason: str | None = None
    version: int
    updated_by: str
    updated_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemAssistantView:
    """Um Assistant de sistema para a administração: o que o YAML define, o que foi sobreposto e o que vale."""

    name: str
    description: str | None = None
    visibility: Literal["public", "private"]
    flow: str | None = None
    status: AssistantStatus
    overridable: frozenset[OverrideSection] = frozenset()
    yaml_models: Mapping[ModelRole, ModelRef] = field(default_factory=lambda: MappingProxyType({}))
    allow: tuple[str, ...] = ()
    yaml_mcp: McpOverride = field(default_factory=McpOverride)
    overrides: tuple[OverrideView, ...] = ()
    effective_models: Mapping[ModelRole, ModelRef] = field(default_factory=lambda: MappingProxyType({}))
    effective_mcp: McpOverride = field(default_factory=McpOverride)
    yaml_vision: frozenset[ModelRole] = frozenset()
    """Papéis com `vision` no YAML e na definição efetiva (ADR-044, item 10)."""
    effective_vision: frozenset[ModelRole] = frozenset()
    required_roles: tuple[ModelRole, ...] = ()
    yaml_auth: AuthOverride = field(default_factory=AuthOverride)
    effective_auth: AuthOverride = field(default_factory=AuthOverride)

    def __post_init__(self) -> None:
        object.__setattr__(self, "overridable", frozenset(self.overridable))
        object.__setattr__(self, "yaml_models", MappingProxyType(dict(self.yaml_models)))
        object.__setattr__(self, "effective_models", MappingProxyType(dict(self.effective_models)))
        object.__setattr__(self, "allow", tuple(self.allow))
        object.__setattr__(self, "overrides", tuple(self.overrides))
        object.__setattr__(self, "required_roles", tuple(self.required_roles))


@dataclass(frozen=True, slots=True, kw_only=True)
class OverrideHistoryEntry:
    """Uma gravação ou um descarte de sobreposição (FR-021)."""

    section: OverrideSection
    action: OverrideAction
    payload: OverridePayload | None = None
    version: int
    actor: str
    at: datetime


# ---------------------------------------------------------------------------------------------------------------------
# Seams
# ---------------------------------------------------------------------------------------------------------------------


class Authenticator(Protocol):
    """Elo 0: quem está pedindo. A forma é a da porta que a 008 já declarou (research R1)."""

    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None:
        """Principal, ou `None` para credencial ausente, inválida ou revogada. **Nunca levanta.**

        `credential` é o token puro: extraí-lo do cabeçalho HTTP é da 008.
        """
        ...


class GrantResolver(Protocol):
    """Elos 2, 6 e 7: o que a execução pode usar."""

    async def resolve(self, *, model: str, principal: Principal) -> ExecutionGrant:
        """`model`: `<assistant>`, `<assistant>/<modelo>` ou `<assistant>/<provider>/<modelo>`.

        Levanta `AssistantNotFound`, `AssistantUnavailable`, `RequestRejected` ou `RateLimited`, nessa ordem de
        verificação (research R4).
        """
        ...


class AssistantDirectory(Protocol):
    """Elo 1 (descoberta) e gestão dos Assistants de usuário."""

    async def discover(self, principal: Principal) -> Sequence[AssistantSummary]:
        """Exatamente o que `resolve` aceitaria para este Principal (FR-008)."""
        ...

    async def mine(self, principal: Principal) -> Sequence[UserAssistant]:
        """Os Assistants do próprio Principal, inclusive indisponíveis, com o motivo."""
        ...

    async def get(self, principal: Principal, name: str) -> UserAssistant: ...

    async def create(self, principal: Principal, draft: UserAssistantDraft) -> UserAssistant: ...

    async def update(self, principal: Principal, name: str, draft: UserAssistantDraft) -> UserAssistant: ...

    async def delete(self, principal: Principal, name: str) -> None: ...


class ApiKeyAdmin(Protocol):
    """Administração de chaves pela superfície privada. Ator fora do grupo de administração recebe `NotFound`."""

    async def issue(
        self,
        *,
        actor: Principal,
        subject: str,
        groups: Collection[str] = (),
        label: str | None = None,
    ) -> IssuedApiKey: ...

    async def keys(self, *, actor: Principal) -> Sequence[ApiKeyInfo]: ...

    async def revoke(self, *, actor: Principal, key_id: str) -> ApiKeyInfo: ...

    async def rotate(self, *, actor: Principal, key_id: str) -> IssuedApiKey:
        """Segredo novo para a mesma chave, mostrado só aqui; o anterior deixa de autenticar na chamada seguinte, sem
        janela (ADR-040). Inexistente: `NotFound`; revogada: `Conflict`."""
        ...


class SystemAssistantAdmin(Protocol):
    """Sobreposições de Assistants de sistema — consumido pela 008 (superfície de administração, ADR-031/032).

    Ator fora do grupo de administração, ou Assistant inexistente ou de usuário: `NotFound`. Seção fora de `overrides`
    no YAML: `RequestRejected` com "só muda por novo deploy". Versão desatualizada: `Conflict` com a guardada. Vale na
    resolução seguinte, sem restart.
    """

    async def system_assistants(self, *, actor: Principal) -> tuple[SystemAssistantView, ...]: ...

    async def system_assistant(self, name: str, *, actor: Principal) -> SystemAssistantView: ...

    async def override_models(
        self, name: str, override: ModelsOverride, *, actor: Principal, version: int | None
    ) -> SystemAssistantView: ...

    async def override_mcp(
        self, name: str, override: McpOverride, *, actor: Principal, version: int | None
    ) -> SystemAssistantView: ...

    async def override_auth(
        self, name: str, override: AuthOverride, *, actor: Principal, version: int | None
    ) -> SystemAssistantView:
        """Esquemas e `allow` (ADR-040): `schemes` e `allow` não vazios, seletores válidos e `*` só em público, senão
        `RequestRejected` nomeando `auth.schemes` ou `auth.allow`. Não confere se subjects e grupos existem."""
        ...

    async def discard_override(
        self, name: str, section: OverrideSection, *, actor: Principal, version: int
    ) -> SystemAssistantView: ...

    async def history(self, name: str, *, actor: Principal) -> tuple[OverrideHistoryEntry, ...]: ...

    async def declared_models(self) -> tuple[ModelRef, ...]:
        """Os modelos efetivos de todos os Assistants de sistema, para a saúde (011)."""
        ...
