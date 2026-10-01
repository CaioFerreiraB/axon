"""Autenticação na borda: o token vem de `Authorization: Bearer <token>` e a verificação é da 003 (research R15).

O mesmo cabeçalho nas duas superfícies — é o que os SDKs da OpenAI enviam com `api_key` —, e a superfície decide o
esquema aceito (a 003 recusa token OIDC na privada e chave na pública).
"""

from __future__ import annotations

import logging
from typing import Final

from fastapi import Request

from ai_core.assistants.api import Authenticator, Principal
from ai_core.http.adapters.errors import ApiError
from ai_core.http.domain.errors import storage_unavailable, unauthenticated

logger: Final = logging.getLogger("ai_core.http")


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
    return principal
