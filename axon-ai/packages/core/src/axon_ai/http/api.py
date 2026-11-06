"""Seam Python da 008 (incremento 9.7; ADR-058 item 2; research R71): o apagamento das conversas de um subject.

A 008 é o adapter primário da plataforma; este é o único seam que ela publica para outro módulo — consumido só pela
composition root (011), que o liga ao apagamento de contas da 012. Não importa o resto do módulo (import-linter).
Contrato em specs/008-core-http-api/contracts/conversations.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True, kw_only=True)
class ConversationErasureReport:
    """O que o apagamento de um subject tirou da 008. Repetido, vai a zero."""

    conversations: int = 0
    """Conversas do dono apagadas, com as mensagens."""
    attachments: int = 0
    """Imagens guardadas nessas conversas."""


class ConversationErasure(Protocol):
    """Apaga todas as conversas de um subject, com as mensagens e as imagens (FR-053). Não confere quem pede: a
    autorização é de quem chama. Idempotente. Sem pseudônimo: nada da conversa fica."""

    async def erase_subject(self, subject: str) -> ConversationErasureReport:
        """`subject` fora de `user:…`/`svc:…` levanta `RequestRejected(field="subject")` antes de tocar dados."""
        ...
