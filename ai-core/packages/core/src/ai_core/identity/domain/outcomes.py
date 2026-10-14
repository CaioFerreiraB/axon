"""Desfechos dos passos do protocolo, do serviço para o adapter HTTP (contracts/oidc.md, contracts/pages.md).

O serviço decide; o adapter só traduz cada desfecho em página, redirecionamento, cookie ou JSON. Nenhum desfecho carrega
segredo além do que precisa ir ao navegador (o id do pedido e o CSRF no formulário, o token da sessão no cookie).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from ai_core.identity.api import Account

type LoginError = Literal["invalid", "google_unknown", "google_refused"]


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginForm:
    """A página de login de um pedido pendente. `error` presente = status 401."""

    request: str
    csrf: str
    google: bool
    identifier: str = ""
    error: LoginError | None = None
    google_email: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PasswordForm:
    """Troca obrigatória da senha temporária, antes de qualquer código."""

    request: str
    csrf: str
    errors: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountPage:
    """ "Minha conta". `csrf` ausente = conta só Google (sem formulário de senha)."""

    account: Account
    csrf: str | None
    message: str | None = None
    errors: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class Redirect:
    location: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SignedIn:
    """Sessão criada: o adapter grava o cookie e redireciona."""

    session_token: str
    max_age: int
    location: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorPage:
    status: int
    title: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LoggedOut:
    """Sessão encerrada: o adapter apaga o cookie e redireciona, ou mostra "Você saiu" sem `location`."""

    location: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenResponse:
    """Resposta JSON do `token` ou do `revoke` (RFC 6749 §5)."""

    status: int
    body: Mapping[str, object]


def token_error(error: str, description: str, *, status: int = 400) -> TokenResponse:
    return TokenResponse(status=status, body={"error": error, "error_description": description})


EXPIRED = ErrorPage(status=400, title="O link de login expirou", message="Volte ao aplicativo e entre de novo.")
FORM_REJECTED = ErrorPage(
    status=403,
    title="Não foi possível conferir o formulário",
    message="Volte ao aplicativo e entre de novo.",
)
GOOGLE_UNAVAILABLE = ErrorPage(
    status=404,
    title="O login com Google não está disponível",
    message="Entre com o seu usuário e senha.",
)
