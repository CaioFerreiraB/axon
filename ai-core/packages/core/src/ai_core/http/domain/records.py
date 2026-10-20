"""Value objects de conversa e de saúde (research R21, R23): puros, usados pelas regras de `domain/` e pelas portas.

Moram em `domain/` para que as regras os usem sem importar `ports.py` (a camada vai de fora para dentro); `ports.py`
os reexporta para quem implementa as portas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from axon_ai_contracts import JSONValue

type MessageRole = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Conversation:
    """Uma conversa. O dono é o subject do Principal: o mesmo subject a alcança pelas duas superfícies (R21)."""

    id: str
    owner: str
    assistant: str
    model: str
    created_at: datetime
    last_activity_at: datetime
    message_count: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredMessage:
    """Uma mensagem gravada. Só `user` e `assistant`: o histórico armazenado é a fonte de verdade (FR-013)."""

    role: MessageRole
    content: str
    at: datetime
    request_id: str
    citations: tuple[JSONValue, ...] = ()
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "flags", tuple(self.flags))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConversationPage:
    """Uma página da listagem, da atividade mais recente para a mais antiga. O cursor é opaco."""

    items: tuple[Conversation, ...]
    next_cursor: str | None = None


type HealthStatus = Literal["ok", "degraded", "down"]


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthItem:
    """Um item conferido. `critical`: se falha, a instância está fora do ar — não só degradada (011 FR-012)."""

    name: str
    ok: bool
    critical: bool = False
    detail: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthReport:
    """Saúde agregada da plataforma. Montada fora deste módulo — pela composition root (011) —, só serializada aqui."""

    items: tuple[HealthItem, ...]

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.items)

    @property
    def status(self) -> HealthStatus:
        """`down` se algum item crítico falha; `degraded` se só não críticos; `ok` se nenhum (011 FR-012)."""
        if any(item.critical and not item.ok for item in self.items):
            return "down"
        return "ok" if self.ok else "degraded"
