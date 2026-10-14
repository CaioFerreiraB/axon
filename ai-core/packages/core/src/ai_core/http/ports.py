"""Portas secundárias da API (specs/008-core-http-api/contracts/ports.md).

Na Fase 1, três delas descreviam o que este módulo exigia da 003. Com a 003 implementada, Principal, autenticação,
resolução de grant e os erros de acesso vêm do `api.py` dela (research R13). Ficam aqui só as portas que são da API:
identificadores, relógio, conversas, saúde agregada e a checagem de administrador. Nenhum framework HTTP aparece neste
arquivo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ai_core.assistants.api import Principal, SystemAssistantAdmin
from ai_core.http.domain.records import (
    Conversation,
    ConversationPage,
    HealthItem,
    HealthReport,
    MessageRole,
    StoredMessage,
)
from ai_core.identity.api import AccountAdmin, LoginSettings
from ai_core.llm.api import ModelRouting
from ai_core.observability.api import PriceBook, TraceDestinations, UsageReportSeam

__all__ = [
    "AdminGate",
    "AdminSeams",
    "Clock",
    "Conversation",
    "ConversationPage",
    "ConversationStore",
    "HealthItem",
    "HealthProvider",
    "HealthReport",
    "InstanceBranding",
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


# --- superfície de administração (Fase 9, research R43, R48) -------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class InstanceBranding:
    """Nome e logotipo da instalação (011: `AI_CORE_DISPLAY_NAME` e `AI_CORE_LOGO_FILE`), para o `GET /admin/v1/me`."""

    name: str = "Agentic"
    logo_url: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AdminSeams:
    """Os seams que a superfície de administração traduz (ADR-031). Sem identidade, contas e login ficam de fora."""

    assistants: SystemAssistantAdmin
    models: ModelRouting
    usage: UsageReportSeam
    prices: PriceBook
    destinations: TraceDestinations
    default_timezone: str = "UTC"
    accounts: AccountAdmin | None = None
    login: LoginSettings | None = None
