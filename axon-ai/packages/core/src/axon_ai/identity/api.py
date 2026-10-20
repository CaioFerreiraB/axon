"""Seams da spec 012: administração de contas, ajustes de login e conjunto de chaves públicas.

Contrato em specs/012-core-identity/contracts/identity-api.md; campos e regras em data-model.md.

Único módulo da 012 que outros módulos importam. Depende só da stdlib e não importa o resto do próprio módulo. Não
conhece Assistants, ACL nem quem é admin: só protege o grupo de administração que a composition root lhe informa
(ADR-031).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, Protocol

# ---------------------------------------------------------------------------------------------------------------------
# Vocabulário
# ---------------------------------------------------------------------------------------------------------------------

type ClientType = Literal["confidential", "public"]
type AuthMethod = Literal["pwd", "google"]
type SettingSource = Literal["installation", "runtime", "default"]

USERNAME_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
"""Nome de usuário e de grupo (FR-001, FR-012): minúsculas, sem `@` — o login decide entre usuário e e-mail pelo `@`."""

EMAIL_PATTERN: Final = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
"""Forma mínima de um e-mail já normalizado (sem espaços, um `@`, domínio com ponto)."""

EMAIL_MAX: Final = 254
PASSWORD_MIN: Final = 12
PASSWORD_MAX: Final = 128
"""Senha de 12 a 128 caracteres, contados como código Unicode, sem regra de composição (FR-002)."""

NAME_MAX: Final = 120
"""Nome de exibição."""

ACTOR_PATTERN: Final = re.compile(r"(user|svc):\S+|cli|bootstrap")
"""Quem faz uma operação de administração: um subject, a linha de comando ou o admin inicial."""


def _check_username(field: str, value: str) -> None:
    if not isinstance(value, str) or not USERNAME_PATTERN.fullmatch(value):
        raise ValueError(f"{field} precisa ser minúsculo, começar por letra ou dígito e usar só [a-z0-9._-]: {value!r}")


def _check_email(value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) > EMAIL_MAX
        or value != value.strip().lower()
        or not EMAIL_PATTERN.fullmatch(value)
    ):
        raise ValueError(f"e-mail inválido ou não normalizado: {value!r}")


def _check_name(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > NAME_MAX:
        raise ValueError(f"nome precisa ter de 1 a {NAME_MAX} caracteres")


def _check_groups(groups: frozenset[str]) -> None:
    for group in groups:
        _check_username("grupo", group)


# ---------------------------------------------------------------------------------------------------------------------
# Value objects publicados
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Account:
    """Uma conta da instalação. `id` é o `sub` estável dos tokens; `username` vira o subject `user:<username>`."""

    id: str
    username: str
    email: str
    name: str
    groups: frozenset[str] = frozenset()
    active: bool = True
    temporary_password: bool = False
    has_password: bool = True
    google_linked: bool = False
    created_at: datetime
    updated_at: datetime
    updated_by: str | None = None
    last_login_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id da conta vazio")
        _check_username("usuário", self.username)
        _check_email(self.email)
        _check_name(self.name)
        object.__setattr__(self, "groups", frozenset(self.groups))
        _check_groups(self.groups)
        if self.temporary_password and not self.has_password:
            raise ValueError("conta só Google não tem senha temporária")
        if self.version < 1:
            raise ValueError("versão começa em 1")

    @property
    def subject(self) -> str:
        """O subject que a 003 lê de `preferred_username` (Fase 7 e 012 R10)."""
        return f"user:{self.username}"


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountDraft:
    """Cadastro pela administração. Sem `google_only`, a plataforma gera a senha temporária (FR-002)."""

    username: str
    email: str
    name: str
    groups: frozenset[str] = frozenset()
    google_only: bool = False

    def __post_init__(self) -> None:
        _check_username("usuário", self.username)
        _check_email(self.email)
        _check_name(self.name)
        object.__setattr__(self, "groups", frozenset(self.groups))
        _check_groups(self.groups)


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountPatch:
    """Alteração pela administração; `None` mantém o campo."""

    email: str | None = None
    name: str | None = None
    groups: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.email is not None:
            _check_email(self.email)
        if self.name is not None:
            _check_name(self.name)
        if self.groups is not None:
            object.__setattr__(self, "groups", frozenset(self.groups))
            _check_groups(self.groups)


@dataclass(frozen=True, slots=True, kw_only=True)
class IssuedPassword:
    """A conta e a senha temporária gerada — devolvida só pela operação que a definiu (FR-002)."""

    account: Account
    temporary_password: str

    def __repr__(self) -> str:
        return f"IssuedPassword(account={self.account.username!r}, temporary_password='«redigido»')"


@dataclass(frozen=True, slots=True, kw_only=True)
class Group:
    """Um grupo e quantas contas ativas o integram. O grupo de administração é `protected` (FR-011)."""

    name: str
    members: int = 0
    protected: bool = False

    def __post_init__(self) -> None:
        _check_username("grupo", self.name)
        if self.members < 0:
            raise ValueError("número de membros negativo")


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginSettingsView:
    """Ajustes de login com a origem de cada um (ADR-033). Nunca traz o segredo do cliente Google."""

    google_enabled: bool
    google_source: SettingSource
    google_configured: bool
    google_redirect_uri: str
    google_client_id: str | None = None
    google_hosted_domain: str | None = None
    version: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class Page[T]:
    """Uma página de resultados; `next_cursor` ausente = acabou."""

    items: tuple[T, ...]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------------------------------------------------
# Erros publicados
# ---------------------------------------------------------------------------------------------------------------------


class IdentityError(Exception):
    """Base dos erros da 012. A mensagem é para quem administra; nunca carrega segredo."""


class AccountNotFound(IdentityError):
    pass


class GroupNotFound(IdentityError):
    pass


class Conflict(IdentityError):
    """Nome ou e-mail em uso, ou versão desatualizada. `field` nomeia o que conflitou."""

    def __init__(self, message: str, *, field: str, current_version: int | None = None) -> None:
        super().__init__(message)
        self.field = field
        self.current_version = current_version


class InvalidField(IdentityError):
    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class ProtectedGroup(IdentityError):
    """Apagar o grupo de administração, ou deixá-lo sem nenhum membro ativo (FR-011)."""


class GoogleNotConfigured(IdentityError):
    """Ligar o login Google sem cliente Google na instalação (FR-009)."""


class InstallationDefined(IdentityError):
    """Ajuste definido pela instalação: a administração só o lê (ADR-033)."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


# ---------------------------------------------------------------------------------------------------------------------
# Seams
# ---------------------------------------------------------------------------------------------------------------------


class AccountAdmin(Protocol):
    """Contas e grupos — consumido pela 008 (superfície de administração) e pela linha de comando."""

    async def accounts(
        self, *, query: str | None = None, active: bool | None = True, limit: int = 50, cursor: str | None = None
    ) -> Page[Account]: ...

    async def account(self, username: str) -> Account: ...

    async def create(self, draft: AccountDraft, *, actor: str) -> IssuedPassword | Account: ...

    async def update(self, username: str, patch: AccountPatch, *, actor: str, version: int) -> Account: ...

    async def reset_password(self, username: str, *, actor: str) -> IssuedPassword: ...

    async def disable(self, username: str, *, actor: str) -> Account: ...

    async def enable(self, username: str, *, actor: str) -> Account: ...

    async def unlink_google(self, username: str, *, actor: str) -> Account: ...

    async def groups(self) -> tuple[Group, ...]: ...

    async def create_group(self, name: str, *, actor: str) -> Group: ...

    async def delete_group(self, name: str, *, actor: str) -> None: ...

    async def set_members(self, name: str, usernames: frozenset[str], *, actor: str) -> Group: ...


class LoginSettings(Protocol):
    """Login Google ligado ou desligado — consumido pela 008."""

    async def view(self) -> LoginSettingsView: ...

    async def set_google(self, enabled: bool, *, actor: str, version: int) -> LoginSettingsView: ...


class PublicKeySet(Protocol):
    """As chaves públicas vigentes do emissor — consumido pela 011, que as injeta no verificador da 003 (FR-017)."""

    def jwks(self) -> Mapping[str, object]: ...
