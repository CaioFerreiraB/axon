"""T036 — conformidade da porta `ConversationStore` (contracts/ports.md, "Fase 2"), em memória e contra Postgres."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from axon_ai.http.ports import Conversation, StoredMessage

T0 = datetime(2026, 9, 30, 12, tzinfo=UTC)


def conversa(cid: str = "conv_1", *, owner: str = "user:ana", at: datetime = T0) -> Conversation:
    return Conversation(id=cid, owner=owner, assistant="geral", model="geral", created_at=at, last_activity_at=at)


def mensagem(role: str, content: str, *, at: datetime = T0, **extra: Any) -> StoredMessage:
    return StoredMessage(role=role, content=content, at=at, request_id="req-1", **extra)  # type: ignore[arg-type]


async def test_cria_e_le_no_escopo_do_dono(conversation_store: Any) -> None:
    await conversation_store.create(conversa())
    assert await conversation_store.get("user:ana", "conv_1") == conversa()
    assert await conversation_store.get("user:bia", "conv_1") is None
    assert await conversation_store.messages("user:bia", "conv_1") is None
    assert await conversation_store.get("user:ana", "conv_x") is None


async def test_mensagens_em_ordem_e_atividade_atualizada(conversation_store: Any) -> None:
    await conversation_store.create(conversa())
    depois = T0 + timedelta(minutes=5)
    primeira = (mensagem("user", "oi"), mensagem("assistant", "olá", citations=({"source": "x"},), flags=("f",)))
    segunda = (mensagem("user", "e aí?", at=depois), mensagem("assistant", "tudo", at=depois))
    assert await conversation_store.append("user:ana", "conv_1", primeira, at=T0)
    assert await conversation_store.append("user:ana", "conv_1", segunda, at=depois)

    lidas = await conversation_store.messages("user:ana", "conv_1")
    assert [m.content for m in lidas] == ["oi", "olá", "e aí?", "tudo"]
    assert lidas[1].citations == ({"source": "x"},) and lidas[1].flags == ("f",)
    atual = await conversation_store.get("user:ana", "conv_1")
    assert atual.message_count == 4 and atual.last_activity_at == depois


async def test_append_em_conversa_apagada_ou_alheia_nao_grava(conversation_store: Any) -> None:
    await conversation_store.create(conversa())
    assert not await conversation_store.append("user:bia", "conv_1", (mensagem("user", "x"),), at=T0)
    assert await conversation_store.delete("user:ana", "conv_1")
    assert not await conversation_store.append("user:ana", "conv_1", (mensagem("user", "x"),), at=T0)


async def test_apagar_e_definitivo_e_no_escopo_do_dono(conversation_store: Any) -> None:
    await conversation_store.create(conversa())
    await conversation_store.append("user:ana", "conv_1", (mensagem("user", "oi"),), at=T0)
    assert not await conversation_store.delete("user:bia", "conv_1")
    assert await conversation_store.delete("user:ana", "conv_1")
    assert await conversation_store.get("user:ana", "conv_1") is None
    assert await conversation_store.messages("user:ana", "conv_1") is None
    assert not await conversation_store.delete("user:ana", "conv_1")


async def test_listagem_mais_recente_primeiro_e_paginacao_estavel(conversation_store: Any) -> None:
    for i in range(5):
        await conversation_store.create(conversa(f"conv_{i}", at=T0 + timedelta(minutes=i)))
    await conversation_store.create(conversa("conv_bia", owner="user:bia"))

    primeira = await conversation_store.list("user:ana", limit=2, cursor=None)
    assert [c.id for c in primeira.items] == ["conv_4", "conv_3"] and primeira.next_cursor is not None
    segunda = await conversation_store.list("user:ana", limit=2, cursor=primeira.next_cursor)
    assert [c.id for c in segunda.items] == ["conv_2", "conv_1"]
    terceira = await conversation_store.list("user:ana", limit=2, cursor=segunda.next_cursor)
    assert [c.id for c in terceira.items] == ["conv_0"] and terceira.next_cursor is None
    assert [c.id for c in (await conversation_store.list("user:bia", limit=10, cursor=None)).items] == ["conv_bia"]


async def test_expiracao_apaga_so_as_inativas(conversation_store: Any) -> None:
    await conversation_store.create(conversa("velha", at=T0))
    await conversation_store.create(conversa("nova", at=T0 + timedelta(days=10)))
    await conversation_store.append("user:ana", "velha", (mensagem("user", "oi"),), at=T0)

    assert await conversation_store.delete_inactive(before=T0 + timedelta(days=1)) == 1
    assert await conversation_store.get("user:ana", "velha") is None
    assert await conversation_store.get("user:ana", "nova") is not None


async def test_postgres_sobrevive_a_um_armazenamento_novo(http_pg_pool: Any) -> None:
    """US7 cen. 3: vive no banco, não no processo."""
    from axon_ai.http.adapters.conversations_postgres import PostgresConversationStore

    await PostgresConversationStore(http_pg_pool).create(conversa())
    await PostgresConversationStore(http_pg_pool).append("user:ana", "conv_1", (mensagem("user", "oi"),), at=T0)
    novo = PostgresConversationStore(http_pg_pool)
    assert [m.content for m in await novo.messages("user:ana", "conv_1")] == ["oi"]


async def test_imagens_presas_a_mensagem_so_do_dono_e_em_cascata(conversation_store: Any) -> None:
    """ADR-044, item 9 (R60): metadados na leitura, bytes pela consulta própria, só para o dono; a exclusão e a
    expiração da conversa levam as imagens."""
    from axon_ai.http.ports import StoredAttachment
    from axon_ai_contracts import Attachment

    imagem = Attachment(mime="image/png", data=b"\x89PNG" + b"x" * 40)
    meta = StoredAttachment(id=imagem.id, mime="image/png", size_bytes=len(imagem.data))
    for cid in ("conv_img", "conv_velha"):
        await conversation_store.create(conversa(cid))
        await conversation_store.append(
            "user:ana",
            cid,
            [
                mensagem("user", "veja"),
                mensagem("assistant", f"[imagem {imagem.id} mostrada ao usuário]", attachments=(meta,)),
            ],
            at=T0,
            files=(imagem,),
        )

    (_, resposta) = await conversation_store.messages("user:ana", "conv_img")
    assert resposta.attachments == (meta,)
    assert await conversation_store.attachment("user:ana", "conv_img", imagem.id) == imagem
    assert await conversation_store.attachment("user:bia", "conv_img", imagem.id) is None
    assert await conversation_store.attachment("user:ana", "conv_img", "img-000000000000") is None

    await conversation_store.delete("user:ana", "conv_img")
    assert await conversation_store.attachment("user:ana", "conv_img", imagem.id) is None
    await conversation_store.delete_inactive(before=T0 + timedelta(days=1))
    assert await conversation_store.attachment("user:ana", "conv_velha", imagem.id) is None
