"""T009 — validação da requisição (`domain/request.py`), pura e anterior a qualquer custo."""

from __future__ import annotations

from typing import Any

import pytest
from graph_testkit import Grant, request

from axon_ai.graph.api import FLOW_AGENTIC, FLOW_CHAT, ExecutionRequestInvalid, UnknownFlow
from axon_ai.graph.domain.request import (
    REQUIRED_ROLES,
    TOOL_FLOWS,
    offered,
    question_of,
    required_roles,
    validate,
)

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


# --- Fase 3 (T029; research R16, R25) --------------------------------------------------------------------------------


@pytest.mark.us2
def test_papeis_exigidos_por_flow() -> None:
    assert REQUIRED_ROLES[FLOW_CHAT] == ("generation",)
    assert REQUIRED_ROLES[FLOW_AGENTIC] == ("controller", "generation")
    assert required_roles(FLOW_AGENTIC) == ("controller", "generation")
    assert required_roles("sem_entrada") == ()


@pytest.mark.us2
def test_flows_que_exigem_tools() -> None:
    assert FLOW_AGENTIC in TOOL_FLOWS and FLOW_CHAT not in TOOL_FLOWS


@pytest.mark.us2
def test_sem_gateway_os_flows_de_tool_nao_sao_oferecidos() -> None:
    names = frozenset({FLOW_CHAT, FLOW_AGENTIC})
    assert offered(names, tools=False) == frozenset({FLOW_CHAT})
    assert offered(names, tools=True) == names


# --- Fase 5 (T065; research R40; FR-007a) ----------------------------------------------------------------------------


@pytest.mark.us3
def test_rag_first_exige_so_generation_e_o_controller_e_opcional() -> None:
    from axon_ai.graph.api import FLOW_RAG_FIRST
    from axon_ai.graph.domain.request import optional_roles

    assert REQUIRED_ROLES[FLOW_RAG_FIRST] == ("generation",)
    assert optional_roles(FLOW_RAG_FIRST) == ("controller",)
    assert optional_roles(FLOW_AGENTIC) == () and optional_roles("x") == ()


def test_no_chat_o_controller_e_opcional_e_so_resolvido_com_a_etapa_de_imagem() -> None:
    """ADR-044, item 8 (R51): o `controller` declarado no `chat` decide as imagens anteriores; sem elas, nem é
    resolvido."""
    from axon_ai.graph.domain.request import optional_roles, roles_to_resolve

    assert optional_roles(FLOW_CHAT) == ("controller",)
    declared = {"generation", "controller"}
    assert roles_to_resolve(FLOW_CHAT, declared, image_gate=False) == ("generation",)
    assert roles_to_resolve(FLOW_CHAT, declared, image_gate=True) == ("generation", "controller")
    assert roles_to_resolve(FLOW_CHAT, {"generation"}, image_gate=True) == ("generation",)
    assert roles_to_resolve(FLOW_AGENTIC, declared, image_gate=False) == ("controller", "generation")


@pytest.mark.us3
def test_rag_first_so_existe_com_o_gateway() -> None:
    from axon_ai.graph.api import FLOW_RAG_FIRST

    assert FLOW_RAG_FIRST in TOOL_FLOWS
    names = frozenset({FLOW_CHAT, FLOW_AGENTIC, FLOW_RAG_FIRST})
    assert offered(names, tools=False) == frozenset({FLOW_CHAT})
