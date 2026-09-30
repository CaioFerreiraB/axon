"""Autenticação na borda: o token vem de `Authorization: Bearer <token>` e a verificação é da 003 (research R15).

O mesmo cabeçalho nas duas superfícies — é o que os SDKs da OpenAI enviam com `api_key` —, e a superfície decide o
esquema aceito (a 003 recusa token OIDC na privada e chave na pública).
"""

from __future__ import annotations

from fastapi import Request

from ai_core.assistants.api import Authenticator, Principal
from ai_core.http.adapters.errors import ApiError
from ai_core.http.domain.errors import unauthenticated


def bearer_token(authorization: str | None) -> str | None:
    """O token de um cabeçalho `Bearer`; qualquer outra coisa é credencial ausente."""
    if not authorization:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def authenticated(request: Request, surface: str) -> Principal:
    """O Principal da requisição, ou 401 no envelope da OpenAI."""
    authenticator: Authenticator = request.app.state.authenticator
    principal = await authenticator.authenticate(
        surface=surface, credential=bearer_token(request.headers.get("authorization"))
    )
    if principal is None:
        raise ApiError(unauthenticated())
    return principal
