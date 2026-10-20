"""Registros internos da 012 (data-model.md, "Registros internos"): o que passa pelas portas e pelas regras puras.

Nunca saem do módulo. Segredos de protocolo (pedido pendente, código, sessão, renovação) aparecem só como hash; a chave
privada, só selada (FR-016, ADR-033). `ports.py` os reexporta para os adapters.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from axon_ai.identity.api import Account, AuthMethod, ClientType

type KeyState = Literal["active", "retiring", "retired"]
type RefreshStatus = Literal["active", "rotated", "revoked"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountRecord:
    """A conta com o que nunca sai do módulo: o hash da senha e o `sub` do Google vinculado."""

    account: Account
    password_hash: str | None = None
    google_sub: str | None = None

    def __post_init__(self) -> None:
        if self.account.has_password != (self.password_hash is not None):
            raise ValueError("has_password precisa refletir a presença do hash")
        if self.account.google_linked != (self.google_sub is not None):
            raise ValueError("google_linked precisa refletir a presença do sub do Google")


@dataclass(frozen=True, slots=True, kw_only=True)
class PendingAuthorization:
    """Pedido de autorização aguardando login (10 min).

    `client_id` ausente = login para a própria página "Minha conta". `account_id` presente = a senha já conferiu e falta
    trocar a temporária. `google_state_hash` presente = o fluxo seguiu para o Google.
    """

    id_hash: str
    csrf_hash: str
    client_id: str | None = None
    redirect_uri: str | None = None
    scope: str = "openid"
    state: str | None = None
    nonce: str | None = None
    code_challenge: str | None = None
    account_id: str | None = None
    google_state_hash: str | None = None
    google_nonce: str | None = None
    google_verifier: str | None = None
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizationCode:
    """Código de autorização (60 s, uso único). `family_id` é a família da renovação que sai dele (FR-007)."""

    hash: str
    client_id: str
    session_id: str
    account_id: str
    family_id: str
    redirect_uri: str
    scope: str
    nonce: str | None = None
    code_challenge: str | None = None
    auth_time: datetime
    amr: AuthMethod
    expires_at: datetime
    used_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeUse:
    """Resultado de consumir um código: `reused` = já tinha sido trocado antes."""

    code: AuthorizationCode
    reused: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Session:
    """Sessão no provedor (cookie). Expiração absoluta, contada do login."""

    id_hash: str
    account_id: str
    auth_time: datetime
    amr: AuthMethod
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshToken:
    """Token de renovação, só o hash. Família = tudo o que saiu do mesmo código."""

    hash: str
    family_id: str
    session_id: str
    client_id: str
    account_id: str
    scope: str
    status: RefreshStatus = "active"
    created_at: datetime
    rotated_to: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SigningKey:
    """Chave de assinatura: a pública como JWK, a privada só selada."""

    kid: str
    public_jwk: Mapping[str, object]
    private_sealed: bytes
    state: KeyState
    created_at: datetime
    retiring_since: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratedKey:
    """Par recém-gerado pelo `TokenSigner`; a privada em PEM nunca é gravada sem selar."""

    kid: str
    public_jwk: Mapping[str, object]
    private_pem: bytes

    def __repr__(self) -> str:
        return f"GeneratedKey(kid={self.kid!r}, private_pem='«redigido»')"


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentitySettings:
    """Ajustes de runtime. `google_enabled` ausente = padrão (ligado se configurado)."""

    google_enabled: bool | None = None
    version: int = 0
    updated_by: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Client:
    """Cliente OIDC do `identity.yaml` (contracts/identity-yaml.md)."""

    id: str
    type: ClientType
    audience: str
    redirect_uris: tuple[str, ...]
    post_logout_redirect_uris: tuple[str, ...] = ()
    secret_ref: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class GoogleClient:
    """Cliente Google da instalação. O segredo nunca sai do adapter que o usa."""

    client_id: str
    client_secret: str
    hosted_domain: str | None = None

    def __repr__(self) -> str:
        return f"GoogleClient(client_id={self.client_id!r}, client_secret='«redigido»')"


@dataclass(frozen=True, slots=True, kw_only=True)
class GoogleIdentity:
    """O que o `id_token` do Google, já verificado (assinatura, `iss`, `aud`), afirma."""

    sub: str
    email: str | None
    email_verified: bool
    hosted_domain: str | None = None
    nonce: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BootstrapAdmin:
    """Admin inicial da instalação (FR-018); a senha já lida do arquivo."""

    username: str
    email: str
    password: str

    def __repr__(self) -> str:
        return f"BootstrapAdmin(username={self.username!r}, email={self.email!r}, password='«redigido»')"
