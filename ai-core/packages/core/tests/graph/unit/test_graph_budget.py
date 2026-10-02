"""T034 — teto de contexto (`domain/budget.py`, R22): estimativa determinística e omissão dos resultados antigos."""

from __future__ import annotations

from math import ceil

import pytest

from ai_core.graph.domain.budget import OMITTED, estimate_tokens, exceeds, trim_results
from ai_core_contracts import ChatMessage

pytestmark = pytest.mark.us2


def tool_message(n: int, content: str) -> ChatMessage:
    return {"role": "tool", "content": content, "tool_call_id": f"call-{n}"}


def call_message(n: int) -> ChatMessage:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": f"call-{n}", "name": "generic.calculate", "arguments": '{"expression": "2+2"}'}],
    }


def test_estimativa_por_mensagem_e_ceil_de_caracteres_por_3_mais_4() -> None:
    messages: list[ChatMessage] = [{"role": "user", "content": "a" * 10}, {"role": "system", "content": ""}]
    assert estimate_tokens(messages) == (ceil(10 / 3) + 4) + (0 + 4)


def test_estimativa_conta_nome_e_argumentos_das_chamadas() -> None:
    chars = len("generic.calculate") + len('{"expression": "2+2"}')
    assert estimate_tokens([call_message(1)]) == ceil(chars / 3) + 4


def test_sem_teto_nada_excede() -> None:
    assert not exceeds([{"role": "user", "content": "a" * 100_000}], None)


def test_teto_e_comparado_com_a_estimativa() -> None:
    messages: list[ChatMessage] = [{"role": "user", "content": "a" * 30}]
    assert estimate_tokens(messages) == 14
    assert not exceeds(messages, 14)
    assert exceeds(messages, 13)


def test_sem_teto_as_mensagens_voltam_intactas() -> None:
    messages = [call_message(1), tool_message(1, "x" * 900)]
    trimmed = trim_results(messages, None)
    assert list(trimmed.messages) == messages
    assert (trimmed.omitted, trimmed.overflow) == (0, False)


def test_omite_do_mais_antigo_para_o_mais_novo_ate_caber() -> None:
    messages: list[ChatMessage] = [
        {"role": "user", "content": "pergunta"},
        call_message(1),
        tool_message(1, "a" * 900),
        call_message(2),
        tool_message(2, "b" * 900),
        call_message(3),
        tool_message(3, "c" * 90),
    ]
    sem_o_primeiro = [*messages[:2], tool_message(1, OMITTED), *messages[3:]]
    ceiling = estimate_tokens(sem_o_primeiro) + 1
    trimmed = trim_results(messages, ceiling)
    assert trimmed.omitted == 1
    assert trimmed.overflow is False
    assert [m["content"] for m in trimmed.messages if m["role"] == "tool"] == [OMITTED, "b" * 900, "c" * 90]
    assert [m["role"] for m in trimmed.messages] == [m["role"] for m in messages]


def test_continua_omitindo_ate_caber() -> None:
    messages = [call_message(1), tool_message(1, "a" * 900), call_message(2), tool_message(2, "b" * 900)]
    ceiling = estimate_tokens([call_message(1), tool_message(1, OMITTED), call_message(2), tool_message(2, OMITTED)])
    trimmed = trim_results(messages, ceiling)
    assert trimmed.omitted == 2 and trimmed.overflow is False


def test_quando_nem_sem_resultados_cabe_e_excesso() -> None:
    messages: list[ChatMessage] = [{"role": "user", "content": "p" * 3000}, call_message(1), tool_message(1, "a" * 90)]
    trimmed = trim_results(messages, 50)
    assert trimmed.omitted == 1
    assert trimmed.overflow is True
    assert trimmed.messages[0] == messages[0]


def test_nunca_altera_mensagens_que_nao_sao_de_tool() -> None:
    messages: list[ChatMessage] = [{"role": "system", "content": "s" * 600}, {"role": "user", "content": "u" * 600}]
    trimmed = trim_results(messages, 10)
    assert list(trimmed.messages) == messages
    assert trimmed.omitted == 0 and trimmed.overflow is True


def test_a_marca_de_omissao() -> None:
    assert OMITTED == "[resultado omitido: teto de contexto]"
