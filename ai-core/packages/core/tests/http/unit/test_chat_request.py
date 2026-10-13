"""T007 — leitura do corpo de chat completions (`domain/chat_request.py`), pura."""

from __future__ import annotations

from typing import Any

import pytest
from http_testkit import MODEL_ID, body

from ai_core.http.domain.chat_request import ChatRequestInvalid, parse


def test_corpo_minimo() -> None:
    request = parse(body())
    assert request.model == MODEL_ID
    assert request.stream is False
    assert request.messages[0]["content"] == "qual é a capital?"


def test_stream_verdadeiro_e_lido() -> None:
    assert parse(body(stream=True)).stream is True


@pytest.mark.parametrize("field", ["tools", "functions", "tool_choice", "function_call"])
def test_campo_de_ampliacao_e_rejeitado_nomeando_o_campo(field: str) -> None:
    """Princípio IV: capacidade vem do Assistant; a requisição só pode restringir."""
    with pytest.raises(ChatRequestInvalid, match=field):
        parse(body(**{field: [{"type": "function"}]}))


@pytest.mark.parametrize("field", ["reference_time", "reference_date", "as_of"])
def test_data_de_referencia_e_rejeitada_nomeando_o_campo(field: str) -> None:
    """FR-012: avaliação fixa a data em processo, nunca pela API."""
    with pytest.raises(ChatRequestInvalid, match=field):
        parse(body(**{field: "2026-01-01"}))


def test_campo_de_ampliacao_nulo_nao_bloqueia() -> None:
    """Clientes mandam `tools: null` com frequência; recusar isso quebraria compatibilidade sem ganho."""
    assert parse(body(tools=None)).model == MODEL_ID


@pytest.mark.parametrize("value", [None, "", "   "])
def test_model_obrigatorio(value: Any) -> None:
    corpo = body()
    corpo["model"] = value
    with pytest.raises(ChatRequestInvalid, match="model"):
        parse(corpo)


def test_model_ausente() -> None:
    corpo = body()
    del corpo["model"]
    with pytest.raises(ChatRequestInvalid, match="model"):
        parse(corpo)


def test_messages_vazia() -> None:
    with pytest.raises(ChatRequestInvalid, match="messages"):
        parse(body(messages=[]))


def test_sem_mensagem_de_usuario() -> None:
    with pytest.raises(ChatRequestInvalid, match="user"):
        parse(body(messages=[{"role": "system", "content": "só instrução"}]))


def test_mensagem_de_usuario_vazia_nao_conta() -> None:
    with pytest.raises(ChatRequestInvalid, match="user"):
        parse(body(messages=[{"role": "user", "content": "   "}]))


def test_mensagem_malformada() -> None:
    with pytest.raises(ChatRequestInvalid):
        parse(body(messages=[{"role": "user"}]))


def test_parametros_de_amostragem_sao_aceitos_e_ignorados() -> None:
    """Entram com os limites do Assistant na Fase 2; recusá-los agora quebraria clientes padrão."""
    request = parse(body(temperature=0.2, top_p=0.9, max_tokens=128))
    assert request.model == MODEL_ID


def test_stream_nao_booleano() -> None:
    with pytest.raises(ChatRequestInvalid, match="stream"):
        parse(body(stream="yes"))


# --- Fase 7 (T067): pedido efêmero, cabeçalho `x-ai-core-store` (FR-023, R37) ---------------------------------------


@pytest.mark.us8
@pytest.mark.parametrize(("value", "conversation"), [(None, None), ("true", None), ("TRUE", "conv_1"), (None, "c")])
def test_store_grava_por_padrao(value: str | None, conversation: str | None) -> None:
    from ai_core.http.domain.chat_request import parse_store

    assert parse_store(value, conversation) is True


@pytest.mark.us8
@pytest.mark.parametrize("value", ["false", "False", " FALSE "])
def test_store_false_sem_conversa_e_efemero(value: str) -> None:
    from ai_core.http.domain.chat_request import parse_store

    assert parse_store(value, None) is False


@pytest.mark.us8
def test_store_false_com_conversa_e_conflito() -> None:
    from ai_core.http.domain.chat_request import STORE_HEADER, parse_store

    with pytest.raises(ChatRequestInvalid) as caught:
        parse_store("false", "conv_1")
    assert (caught.value.code, caught.value.field) == ("store_conflict", STORE_HEADER)


@pytest.mark.us8
@pytest.mark.parametrize("value", ["talvez", "", "0"])
def test_store_com_valor_desconhecido_e_recusado(value: str) -> None:
    from ai_core.http.domain.chat_request import STORE_HEADER, parse_store

    with pytest.raises(ChatRequestInvalid) as caught:
        parse_store(value, None)
    assert (caught.value.code, caught.value.field) == ("invalid_header", STORE_HEADER)


@pytest.mark.us8
def test_parse_le_o_cabecalho() -> None:
    assert parse(body(), store_header="false").store is False
    assert parse(body()).store is True
    with pytest.raises(ChatRequestInvalid, match="x-ai-core-store"):
        parse(body(conversation_id="conv_1"), store_header="false")
