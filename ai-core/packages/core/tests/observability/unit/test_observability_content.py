"""T050 — o conteúdo opcional redigido e cortado (ADR-034, research R29)."""

from __future__ import annotations

import pytest
from trace_testkit import AT, exchange

from ai_core.observability.api import ExchangeMessage
from ai_core.observability.domain.content import CONTENT_MAX, exchange_record, redact_content

pytestmark = pytest.mark.us7


def test_credenciais_sao_redigidas_e_o_resto_fica() -> None:
    record = exchange_record(exchange(), AT)
    assert record.type == "model_exchange" and record.request_id == "req-7f3a"
    messages = record.attributes["messages"]
    assert isinstance(messages, list)
    assert messages[0] == {"role": "system", "content": "Você é útil."}
    assert "sk-segredo-123" not in str(messages[1]) and "qual é a capital?" in str(messages[1])
    assert record.attributes["output"] == "Brasília." and record.attributes["model"] == "qwen3:1.7b"


def test_cada_mensagem_e_a_saida_cortadas_em_16_kib_com_marca() -> None:
    long = "a" * (CONTENT_MAX + 50)
    record = exchange_record(exchange(messages=(ExchangeMessage(role="user", content=long),), output=long), AT)
    content = record.attributes["messages"][0]["content"]  # type: ignore[index]
    assert len(content) < CONTENT_MAX + 60 and content.endswith("[truncado: 50 caracteres]")  # type: ignore[union-attr]
    assert str(record.attributes["output"]).endswith("[truncado: 50 caracteres]")


def test_texto_curto_passa_inteiro() -> None:
    assert redact_content("x" * 5_000) == "x" * 5_000  # o limite do trace comum (2 000) não vale aqui
