"""T012b — a prova direta da SC-004: um cliente OpenAI **real** conversa com a plataforma sem adaptação.

O SDK já está no ambiente por ser o adapter da 006; aqui ele é o cliente, não o servidor. O transporte ASGI liga o SDK
à app em processo: nenhuma porta aberta, nenhuma rede.
"""

from __future__ import annotations

from typing import Any

import httpx2
import pytest
from graph_testkit import RecordingTraceSink
from http_testkit import MODEL_ID, app
from openai import AsyncOpenAI, NotFoundError

MESSAGES: list[Any] = [{"role": "user", "content": "qual é a capital?"}]


@pytest.fixture
def client() -> AsyncOpenAI:
    plataforma = app(trace=RecordingTraceSink())
    return AsyncOpenAI(
        api_key="nao-usado",
        base_url="http://plataforma.test/v1",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.ASGITransport(app=plataforma)),
    )


async def test_cliente_openai_padrao_conversa_em_streaming(client: AsyncOpenAI) -> None:
    pedacos: list[str] = []
    stream = await client.chat.completions.create(model=MODEL_ID, messages=MESSAGES, stream=True)
    async for chunk in stream:
        conteudo = chunk.choices[0].delta.content if chunk.choices else None
        if conteudo:
            pedacos.append(conteudo)

    assert "".join(pedacos) == "Brasília"


async def test_cliente_openai_padrao_conversa_sem_streaming(client: AsyncOpenAI) -> None:
    resposta = await client.chat.completions.create(model=MODEL_ID, messages=MESSAGES)
    assert resposta.choices[0].message.content == "Brasília"
    assert resposta.choices[0].finish_reason == "stop"
    assert resposta.id.startswith("chatcmpl-")


async def test_o_sdk_entende_o_desfecho_e_o_papel(client: AsyncOpenAI) -> None:
    """Se o papel viesse em todo chunk, ou o desfecho em todos, o SDK reclamaria aqui."""
    papeis: list[str] = []
    desfechos: list[str] = []
    stream = await client.chat.completions.create(model=MODEL_ID, messages=MESSAGES, stream=True)
    async for chunk in stream:
        if not chunk.choices:
            continue
        if chunk.choices[0].delta.role:
            papeis.append(chunk.choices[0].delta.role)
        if chunk.choices[0].finish_reason:
            desfechos.append(chunk.choices[0].finish_reason)

    assert papeis == ["assistant"]
    assert desfechos == ["stop"]


async def test_assistant_desconhecido_vira_erro_de_nao_encontrado_no_sdk(client: AsyncOpenAI) -> None:
    with pytest.raises(NotFoundError):
        await client.chat.completions.create(model="nao-existe", messages=MESSAGES)
