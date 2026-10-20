"""Validação do pedido de autorização (FR-004, FR-005; contracts/oidc.md, `GET /oauth2/authorize`).

Duas famílias de erro: com cliente ou `redirect_uri` inválidos, **nunca** se redireciona (página de erro); com eles
válidos, o erro volta ao cliente pelo `redirect_uri` (RFC 6749 §4.1.2.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from axon_ai.identity.domain.pkce import is_challenge
from axon_ai.identity.domain.records import Client

KNOWN_SCOPES: Final = ("openid", "profile", "email", "groups", "offline_access")
STATE_MAX: Final = 1024
NONCE_MAX: Final = 512

type Prompt = Literal["login", "none"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizationRequest:
    client: Client
    redirect_uri: str
    scope: str
    nonce: str
    state: str | None = None
    code_challenge: str | None = None
    prompt: Prompt | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NoRedirect:
    """Cliente ou `redirect_uri` inválidos: página de erro com o motivo curto."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RedirectError:
    redirect_uri: str
    error: str
    description: str
    state: str | None = None


def read_authorization(
    params: Mapping[str, str], clients: Mapping[str, Client]
) -> AuthorizationRequest | NoRedirect | RedirectError:
    client = clients.get(params.get("client_id", ""))
    if client is None:
        return NoRedirect(reason="O aplicativo que pediu o login não é conhecido por esta instalação.")
    redirect_uri = params.get("redirect_uri", "")
    if redirect_uri not in client.redirect_uris:
        return NoRedirect(reason="O endereço de retorno não está registrado para este aplicativo.")
    state = params.get("state") or None

    def refuse(error: str, description: str) -> RedirectError:
        return RedirectError(redirect_uri=redirect_uri, error=error, description=description, state=state)

    if state is not None and len(state) > STATE_MAX:
        return refuse("invalid_request", "state longo demais")
    if params.get("response_type") != "code":
        return refuse("unsupported_response_type", "só response_type=code")
    requested = params.get("scope", "").split()
    if "openid" not in requested:
        return refuse("invalid_scope", "o escopo precisa conter openid")
    scope = " ".join(dict.fromkeys(item for item in requested if item in KNOWN_SCOPES))
    nonce = params.get("nonce", "")
    if not nonce:
        return refuse("invalid_request", "nonce obrigatório")
    if len(nonce) > NONCE_MAX:
        return refuse("invalid_request", "nonce longo demais")
    challenge = params.get("code_challenge") or None
    method = params.get("code_challenge_method") or None
    if challenge is None:
        if client.type == "public":
            return refuse("invalid_request", "PKCE S256 obrigatório para cliente público")
        if method is not None:
            return refuse("invalid_request", "code_challenge_method sem code_challenge")
    elif method != "S256" or not is_challenge(challenge):
        return refuse("invalid_request", "só PKCE S256, com desafio de 43 caracteres")
    prompts = set(params.get("prompt", "").split())
    prompt: Prompt | None = None
    if "none" in prompts:
        if len(prompts) > 1:
            return refuse("invalid_request", "prompt=none não combina com outros valores")
        prompt = "none"
    elif "login" in prompts:
        prompt = "login"
    return AuthorizationRequest(
        client=client,
        redirect_uri=redirect_uri,
        scope=scope,
        nonce=nonce,
        state=state,
        code_challenge=challenge,
        prompt=prompt,
    )
