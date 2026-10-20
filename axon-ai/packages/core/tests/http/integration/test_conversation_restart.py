"""T038 — conversa continuada depois de um "reinício" (US7 cen. 3, SC-005): um serviço novo sobre o mesmo
armazenamento. Contra Postgres, é o banco que guarda — o processo pode morrer.

Cliente HTTP assíncrono no mesmo laço de eventos do teste: o pool do Postgres pertence ao laço em que foi aberto.
"""

from __future__ import annotations

from typing import Any

import httpx
from graph_testkit import provider
from http_testkit import ANA_TOKEN, Platform, bearer

from axon_ai.http.adapters.conversations_postgres import PostgresConversationStore


def _client(platform: Platform) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=platform.app), base_url="http://axon-ai")


async def _chat(client: httpx.AsyncClient, content: str, **extra: Any) -> httpx.Response:
    return await client.post(
        "/v1/chat/completions",
        headers=bearer(ANA_TOKEN),
        json={"model": "geral", "messages": [{"role": "user", "content": content}]} | extra,
    )


async def test_continua_depois_de_um_servico_novo_sobre_o_mesmo_armazenamento(conversation_store: Any) -> None:
    async with _client(Platform(conversations=conversation_store)) as antes:
        cid = (await _chat(antes, "primeira")).headers["x-conversation-id"]

    llm = provider()
    async with _client(Platform(llm=llm, conversations=conversation_store)) as depois:
        assert (await _chat(depois, "segunda", conversation_id=cid)).status_code == 200
    enviadas = [m["content"] for m in llm.calls[-1]["messages"] if m["role"] != "system"]
    assert enviadas == ["primeira", "Brasília", "segunda"]


async def test_postgres_com_adapter_novo(http_pg_pool: Any) -> None:
    async with _client(Platform(conversations=PostgresConversationStore(http_pg_pool))) as antes:
        cid = (await _chat(antes, "primeira")).headers["x-conversation-id"]
    async with _client(Platform(conversations=PostgresConversationStore(http_pg_pool))) as depois:
        lida = (await depois.get(f"/v1/conversations/{cid}", headers=bearer(ANA_TOKEN))).json()
    assert [m["content"] for m in lida["messages"]] == ["primeira", "Brasília"]
