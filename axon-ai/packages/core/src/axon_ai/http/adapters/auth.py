"""Autenticação na borda: o token vem de `Authorization: Bearer <token>` e a verificação é da 003 (research R15).

O mesmo cabeçalho nas duas superfícies — é o que os SDKs da OpenAI enviam com `api_key` —, e a superfície decide o
esquema aceito (a 003 recusa token OIDC na privada e chave na pública).
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Final

from fastapi import Request

from axon_ai.assistants.api import Authenticator, NotFound, Principal
from axon_ai.http.adapters.errors import ApiError
from axon_ai.http.domain.errors import storage_unavailable, unauthenticated
from axon_ai.http.domain.scopes import key_reaches

logger: Final = logging.getLogger("axon_ai.http")


def bearer_token(authorization: str | None) -> str | None:
    """O token de um cabeçalho `Bearer`; qualquer outra coisa é credencial ausente."""
    if not authorization:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def authenticated(request: Request, surface: str) -> Principal:
    """O Principal da requisição; 401 se a credencial é recusada, 503 se o armazenamento dela falha (FR-021)."""
    authenticator: Authenticator = request.app.state.authenticator
    try:
        principal = await authenticator.authenticate(
            surface=surface, credential=bearer_token(request.headers.get("authorization"))
        )
    except Exception as error:
        # A 003 só levanta quando o armazenamento falha — credencial ruim é `None`. Responder 401 culparia a
        # credencial; o 503 diz a verdade, e a causa fica no log do operador, não no corpo (FR-021).
        logger.exception("autenticação indisponível: o armazenamento de credenciais falhou")
        raise ApiError(storage_unavailable()) from error
    if principal is None:
        raise ApiError(unauthenticated())
    required = getattr(request.state, SCOPES_STATE, None)
    if required is not None and not key_reaches(principal.scopes, required):
        # Faltar o escopo é o 404 de rota inexistente, antes de qualquer seam (ADR-057 item 5; FR-047).
        raise NotFound(ROUTE_NOT_FOUND)
    return principal


SCOPES_ATTRIBUTE: Final = "axon_scopes"
"""A marca no endpoint montado, que a suíte do mapa confere (SC-012; research R66)."""
SCOPES_STATE: Final = "axon_route_scopes"
ROUTE_NOT_FOUND: Final = "recurso não encontrado"

type Endpoint = Callable[..., Awaitable[Any]]


def scoped(route_scopes: frozenset[str]) -> Callable[[Endpoint], Endpoint]:
    """Declara os escopos de chave que alcançam a rota (FR-046). Marca o endpoint e põe o conjunto na requisição, onde
    `authenticated` o aplica — a declaração e a regra são o mesmo objeto. Fica entre o `@router.<método>` e a função."""

    def decorate(handler: Endpoint) -> Endpoint:
        @functools.wraps(handler)
        async def endpoint(*args: Any, **kwargs: Any) -> Any:
            request = kwargs.get("request") or next(arg for arg in args if isinstance(arg, Request))
            setattr(request.state, SCOPES_STATE, route_scopes)
            return await handler(*args, **kwargs)

        setattr(endpoint, SCOPES_ATTRIBUTE, route_scopes)
        return endpoint

    return decorate
