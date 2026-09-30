"""Portas secundárias da API (specs/008-core-http-api/contracts/ports.md).

Na Fase 1, três delas descreviam o que este módulo exigia da 003. Com a 003 implementada, Principal, autenticação,
resolução de grant e os erros de acesso vêm do `api.py` dela (research R13). Ficam aqui só as portas que são da API:
identificadores, relógio, conversas, saúde agregada e a checagem de administrador. Nenhum framework HTTP aparece neste
arquivo.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from ai_core.assistants.api import Principal
from ai_core.http.domain.records import (
    Conversation,
    ConversationPage,
    HealthItem,
    HealthReport,
    MessageRole,
    StoredMessage,
)

__all__ = [
    "AdminGate",
    "Clock",
    "Conversation",
    "ConversationPage",
    "ConversationStore",
    "HealthItem",
    "HealthProvider",
    "HealthReport",
    "MessageRole",
    "RequestIds",
    "StoredMessage",
]


class RequestIds(Protocol):
    """Identificadores: da requisição (cabeçalho, `id` da resposta, chave do trace) e, noutra instância, de conversa."""

    def next(self) -> str:
        """Um identificador novo."""
        ...


class Clock(Protocol):
    """Tempo, por porta (princípio XIII): `created` das respostas e a expiração das conversas."""

    def now(self) -> datetime:
        """Instante atual, sempre com timezone."""
        ...


class ConversationStore(Protocol):
    """Conversas e mensagens, por (dono, id). Toda leitura e escrita é no escopo do dono."""

    async def create(self, conversation: Conversation) -> None: ...

    async def get(self, owner: str, conversation_id: str) -> Conversation | None:
        """`None` para inexistente **ou** de outro dono — a rota responde 404 igual nos dois casos."""
        ...

    async def messages(self, owner: str, conversation_id: str) -> Sequence[StoredMessage] | None:
        """Em ordem de gravação; `None` como em `get`."""
        ...

    async def append(
        self, owner: str, conversation_id: str, messages: Sequence[StoredMessage], *, at: datetime
    ) -> bool:
        """Grava e atualiza a última atividade. `False` se a conversa foi apagada — a troca não é gravada (FR-018)."""
        ...

    async def list(self, owner: str, *, limit: int, cursor: str | None) -> ConversationPage: ...

    async def delete(self, owner: str, conversation_id: str) -> bool:
        """Exclusão definitiva, com as mensagens. `False` se não existe ou não é do dono."""
        ...

    async def delete_inactive(self, *, before: datetime) -> int:
        """Expiração: apaga as conversas com última atividade anterior a `before` e devolve quantas."""
        ...


class HealthProvider(Protocol):
    async def health(self) -> HealthReport: ...


class AdminGate(Protocol):
    """Quem administra a superfície privada. A regra é da 003; o `AccessService` dela cumpre esta forma (R20)."""

    def is_admin(self, principal: Principal) -> bool: ...
