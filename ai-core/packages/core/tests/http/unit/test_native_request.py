"""T030 — a requisição nativa é estrita: nomeia o Assistant e, no máximo, restringe (US3;
contracts/native-request.md)."""

from __future__ import annotations

from typing import Any

import pytest

from ai_core.assistants.api import WIDENING_FIELDS
from ai_core.http.domain.errors import InvalidRequest
from ai_core.http.domain.native_request import parse_native

MENSAGENS = [{"role": "user", "content": "oi"}]


def _body(**overrides: Any) -> dict[str, Any]:
    return {"assistant": "geral", "messages": MENSAGENS} | overrides


def test_assistant_sem_restricao() -> None:
    request = parse_native(_body())
    assert (request.model, request.stream, request.conversation_id) == ("geral", False, None)


@pytest.mark.parametrize(
    ("model", "esperado"), [("qwen3:8b", "geral/qwen3:8b"), ("ollama/qwen3:8b", "geral/ollama/qwen3:8b")]
)
def test_assistant_e_model_formam_o_id_completo(model: str, esperado: str) -> None:
    assert parse_native(_body(model=model)).model == esperado


def test_stream_e_conversation_id() -> None:
    request = parse_native(_body(stream=True, conversation_id="conv_1"))
    assert request.stream and request.conversation_id == "conv_1"


@pytest.mark.parametrize("field", sorted(WIDENING_FIELDS))
def test_campo_de_ampliacao_e_recusado_nomeando_o_campo(field: str) -> None:
    with pytest.raises(InvalidRequest) as caught:
        parse_native(_body(**{field: ["x"]}))
    assert (caught.value.field, caught.value.code) == (field, "widening_field")


def test_data_de_referencia_e_recusada() -> None:
    with pytest.raises(InvalidRequest) as caught:
        parse_native(_body(reference_time="2026-01-01"))
    assert caught.value.code == "reference_time"


@pytest.mark.parametrize("field", ["temperature", "user", "n", "extra"])
def test_campo_desconhecido_e_recusado(field: str) -> None:
    with pytest.raises(InvalidRequest) as caught:
        parse_native(_body(**{field: 1}))
    assert caught.value.field == field


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"assistant": ""}, "assistant"),
        ({"assistant": "geral/qwen3"}, "assistant"),
        ({"model": ""}, "model"),
        ({"messages": []}, "messages"),
        ({"stream": "sim"}, "stream"),
        ({"conversation_id": 7}, "conversation_id"),
    ],
)
def test_campo_obrigatorio_ou_mal_formado(overrides: dict[str, Any], field: str) -> None:
    with pytest.raises(InvalidRequest) as caught:
        parse_native(_body(**overrides))
    assert caught.value.field == field
