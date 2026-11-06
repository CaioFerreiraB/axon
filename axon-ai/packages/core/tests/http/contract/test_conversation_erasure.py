"""T147 — apagar as conversas de um subject (incremento 9.7, US14 cen. 1 a 3; FR-053, SC-014; research R71)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from axon_ai.assistants.api import Principal, RequestRejected
from axon_ai.http.adapters.conversations_memory import InMemoryConversationStore
from axon_ai.http.adapters.development import FixedClock
from axon_ai.http.api import ConversationErasure, ConversationErasureReport
from axon_ai.http.ports import Conversation, StoredAttachment, StoredMessage
from axon_ai.http.service import ConversationService
from axon_ai_contracts import Attachment

pytestmark = pytest.mark.us14

T0 = datetime(2026, 11, 5, 12, tzinfo=UTC)
ANA = Principal(subject="user:ana", scheme="oidc")


async def _cenario(store: Any) -> ConversationService:
    for cid, owner, image in (("a1", "user:ana", True), ("a2", "user:ana", False), ("b1", "user:bia", True)):
        await store.create(
            Conversation(id=cid, owner=owner, assistant="geral", model="geral", created_at=T0, last_activity_at=T0)
        )
        files = (Attachment(mime="image/png", data=b"\x89PNG" + cid.encode() * 20),) if image else ()
        metas = tuple(StoredAttachment(id=f.id, mime=f.mime, size_bytes=len(f.data)) for f in files)
        message = StoredMessage(role="assistant", content=f"{owner} disse oi", at=T0, request_id="r", attachments=metas)
        await store.append(owner, cid, [message], at=T0, files=files)
    return ConversationService(store=store, clock=FixedClock(T0))


async def test_cenarios_1_e_2() -> None:
    store = InMemoryConversationStore()
    service = await _cenario(store)
    erasure: ConversationErasure = service

    assert await erasure.erase_subject("user:ana") == ConversationErasureReport(conversations=2, attachments=1)
    assert (await service.page(ANA, limit=10, cursor=None)).items == ()
    assert await store.get("user:bia", "b1") is not None
    assert await erasure.erase_subject("user:ana") == ConversationErasureReport()


@pytest.mark.parametrize("subject", ["", "ana", "user:", "deleted:0123456789abcdef"])
async def test_cenario_3_subject_invalido_sem_tocar_dados(subject: str) -> None:
    store = InMemoryConversationStore()
    service = await _cenario(store)

    with pytest.raises(RequestRejected) as erro:
        await service.erase_subject(subject)

    assert erro.value.field == "subject"
    assert len((await service.page(ANA, limit=10, cursor=None)).items) == 2


async def test_sc_014_nenhuma_linha_do_schema_http_cita_o_subject(http_pg_pool: Any) -> None:
    from axon_ai.http.adapters.conversations_postgres import PostgresConversationStore

    service = await _cenario(PostgresConversationStore(http_pg_pool))
    assert await service.erase_subject("user:ana") == ConversationErasureReport(conversations=2, attachments=1)

    async with http_pg_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'http' "
            "AND data_type IN ('text', 'jsonb', 'ARRAY')"
        )
        columns = await cursor.fetchall()
        achados = []
        for table, column in columns:
            cursor = await connection.execute(
                f"SELECT count(*) FROM http.{table} WHERE {column}::text LIKE %s", ("%user:ana%",)
            )
            (count,) = await cursor.fetchone()
            if count:
                achados.append((table, column, count))
    assert columns and achados == []
