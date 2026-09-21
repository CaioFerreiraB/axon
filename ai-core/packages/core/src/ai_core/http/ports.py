"""Portas secundárias da API (specs/008-core-http-api/contracts/ports.md).

Três delas descrevem o que este módulo **exige** da 003: declará-las aqui é o que permite à autenticação e à resolução
de Assistant chegarem na Fase 2 sem que nenhuma rota mude (research R1, R2). Nenhum framework HTTP aparece neste
arquivo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ai_core.graph.api import ExecutionGrant

PUBLIC_SURFACE = "public"
PRIVATE_SURFACE = "private"


class AssistantNotFound(LookupError):
    """Assistant inexistente **ou** não autorizado.

    Um erro só para os dois casos é deliberado: a rota responde 404 idêntico, e a existência de um Assistant privado
    não vaza (FR-009, regra 404-não-403 da 003).
    """


class Principal(Protocol):
    """Identidade autenticada da requisição. A 003 fornece o valor a partir da Fase 2."""

    @property
    def id(self) -> str:
        """Identificador estável de quem está pedindo."""
        ...


class Authenticator(Protocol):
    """Verificação de credencial por superfície. Consumida como dependência das rotas."""

    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None:
        """Devolve o Principal ou `None` quando a credencial é recusada. NUNCA levanta por credencial ausente."""
        ...


class GrantResolver(Protocol):
    """Resolução de Assistant: decide o que a execução pode fazer (princípio IV)."""

    async def resolve(self, *, model: str, principal: Principal) -> ExecutionGrant:
        """`model` é `"<assistant>"` ou `"<assistant>/<modelo>"`. Levanta `AssistantNotFound`."""
        ...


class RequestIds(Protocol):
    """Identificador da requisição: aparece na resposta (FR-010) e é a chave do trace (009)."""

    def next(self) -> str:
        """Um identificador novo por requisição."""
        ...


class Clock(Protocol):
    """Tempo, por porta (princípio XIII).

    O formato da OpenAI tem um campo `created` em toda resposta e em todo chunk — é por isso que esta fase já lê o
    relógio. A 011 injeta o mesmo adapter nos módulos com porta de tempo.
    """

    def now(self) -> datetime:
        """Instante atual, sempre com timezone."""
        ...
