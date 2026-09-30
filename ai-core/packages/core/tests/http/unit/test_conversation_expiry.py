"""T037 — expiração de conversas com relógio fixo (US7 cen. 7, FR-019, SC-007)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from assistants_testkit import MutableClock

from ai_core.http.adapters.conversations_memory import InMemoryConversationStore
from ai_core.http.ports import Conversation
from ai_core.http.service import DEFAULT_RETENTION, ConversationService

T0 = datetime(2026, 1, 1, 12, tzinfo=UTC)


def _conversa(cid: str, at: datetime) -> Conversation:
    return Conversation(id=cid, owner="user:ana", assistant="geral", model="geral", created_at=at, last_activity_at=at)


async def test_prazo_padrao_e_180_dias() -> None:
    assert timedelta(days=180) == DEFAULT_RETENTION


async def test_apaga_no_prazo_e_nem_um_ciclo_depois() -> None:
    store = InMemoryConversationStore()
    clock = MutableClock(T0)
    service = ConversationService(store=store, clock=clock, retention=timedelta(days=180))
    await store.create(_conversa("antiga", T0))
    await store.create(_conversa("recente", T0 + timedelta(days=100)))

    clock.advance(timedelta(days=180).total_seconds() - 1)
    assert await service.expire() == 0, "ainda dentro do prazo"

    clock.advance(2)
    assert await service.expire() == 1
    assert await store.get("user:ana", "antiga") is None
    assert await store.get("user:ana", "recente") is not None


async def test_prazo_configuravel() -> None:
    store = InMemoryConversationStore()
    clock = MutableClock(T0 + timedelta(days=8))
    await store.create(_conversa("c", T0))
    assert await ConversationService(store=store, clock=clock, retention=timedelta(days=7)).expire() == 1
