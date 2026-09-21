"""T009 — validação da requisição (`domain/request.py`), pura e anterior a qualquer custo."""

from __future__ import annotations

from typing import Any

import pytest
from graph_testkit import Grant, request

from ai_core.graph.api import ExecutionRequestInvalid, UnknownFlow
from ai_core.graph.domain.request import question_of, validate

FLOWS = frozenset({"chat"})


def test_pergunta_e_a_ultima_mensagem_de_usuario() -> None:
    messages: list[Any] = [
        {"role": "user", "content": "primeira"},
        {"role": "assistant", "content": "resposta"},
        {"role": "user", "content": "segunda"},
    ]
    assert question_of(request(messages=messages)) == "segunda"


def test_mensagens_de_sistema_e_assistente_nao_viram_pergunta() -> None:
    messages: list[Any] = [
        {"role": "system", "content": "instrução"},
        {"role": "user", "content": "a pergunta"},
        {"role": "assistant", "content": "rascunho"},
    ]
    assert question_of(request(messages=messages)) == "a pergunta"


def test_requisicao_sem_mensagem_de_usuario_e_invalida() -> None:
    messages: list[Any] = [{"role": "system", "content": "só instrução"}]
    with pytest.raises(ExecutionRequestInvalid):
        question_of(request(messages=messages))


def test_mensagem_de_usuario_vazia_nao_conta() -> None:
    messages: list[Any] = [{"role": "user", "content": "   "}]
    with pytest.raises(ExecutionRequestInvalid):
        question_of(request(messages=messages))


def test_validate_devolve_a_pergunta() -> None:
    assert validate(request(), Grant(), FLOWS) == "qual é a capital?"


def test_flow_inexistente_nomeia_o_pedido_e_os_disponiveis() -> None:
    with pytest.raises(UnknownFlow) as error:
        validate(request(), Grant(flow="agentic"), FLOWS)
    assert "agentic" in str(error.value)
    assert "chat" in str(error.value)


def test_flow_e_conferido_antes_da_pergunta() -> None:
    """Ordem importa: o erro mais barato de diagnosticar aparece primeiro."""
    messages: list[Any] = [{"role": "system", "content": "sem usuário"}]
    with pytest.raises(UnknownFlow):
        validate(request(messages=messages), Grant(flow="nao-existe"), FLOWS)
