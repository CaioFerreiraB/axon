"""T032 — a ação do controller (`domain/actions.py`): o formato pedido ao provider e a leitura da saída (R17, R18)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from graph_testkit import catalog_tool
from hypothesis import given
from hypothesis import strategies as st

from ai_core.graph.domain.actions import (
    CONTROLLER_INSTRUCTION,
    INVALID_REASONS,
    AnswerAction,
    InvalidAction,
    ToolAction,
    action_schema,
    catalog_text,
    parse_action,
    response_format,
    sanitize,
)

pytestmark = pytest.mark.us2


# --- instrução e catálogo -------------------------------------------------------------------------------------------


def test_instrucao_do_controller_e_do_core_e_sem_dominio() -> None:
    texto = CONTROLLER_INSTRUCTION.lower()
    assert '"action"' in texto and "answer" in texto and "tool" in texto
    for dominio in ("escot", "scout", "financ", "saúde"):
        assert dominio not in texto


def test_catalogo_em_texto_lista_nome_descricao_e_parametros() -> None:
    tools = [catalog_tool(), catalog_tool("crm.buscar", description="Busca clientes.", parameters={"type": "object"})]
    linhas = catalog_text(tools).splitlines()
    assert any("generic.calculate" in linha and "Calcula" in linha and '"expression"' in linha for linha in linhas)
    assert any("crm.buscar" in linha and "Busca clientes." in linha for linha in linhas)
    assert catalog_text(tools).index("generic.calculate") < catalog_text(tools).index("crm.buscar")


# --- esquema ------------------------------------------------------------------------------------------------------


def test_esquema_tem_o_ramo_answer_primeiro_e_um_ramo_por_tool_na_ordem() -> None:
    tools = [catalog_tool(), catalog_tool("crm.buscar", parameters={"type": "object"})]
    branches = action_schema(tools)["anyOf"]
    assert branches[0] == {
        "type": "object",
        "properties": {"action": {"const": "answer"}},
        "required": ["action"],
        "additionalProperties": False,
    }
    assert [branch["properties"]["name"]["const"] for branch in branches[1:]] == ["generic.calculate", "crm.buscar"]
    for branch in branches[1:]:
        assert branch["properties"]["action"] == {"const": "tool"}
        assert branch["required"] == ["action", "name", "arguments"]
        assert branch["additionalProperties"] is False
    assert branches[1]["properties"]["arguments"] == dict(catalog_tool().parameters)


def test_catalogo_vazio_so_tem_o_ramo_answer() -> None:
    assert len(action_schema([])["anyOf"]) == 1


def test_formato_de_resposta_embrulha_o_esquema_sem_strict() -> None:
    formato = response_format([catalog_tool()])
    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["name"] == "controller_action"
    assert formato["json_schema"]["schema"] == action_schema([catalog_tool()])
    assert "strict" not in formato["json_schema"]


def test_saneamento_tira_regex_em_qualquer_profundidade_sem_mexer_no_original() -> None:
    original: dict[str, Any] = {
        "type": "object",
        "properties": {
            "codigo": {"type": "string", "pattern": "^(a+)+$"},
            "itens": {"type": "array", "items": {"type": "string", "pattern": "x*"}},
            "mapa": {"type": "object", "patternProperties": {"^k": {"type": "string"}}},
            "pattern": {"type": "string", "description": "um parâmetro que se chama pattern"},
        },
        "anyOf": [{"properties": {"z": {"pattern": "z"}}}],
    }
    copia = json.loads(json.dumps(original))
    limpo = sanitize(original)
    texto = json.dumps(limpo)
    assert '"pattern": "' not in texto
    assert "patternProperties" not in texto
    assert limpo["properties"]["pattern"] == {"type": "string", "description": "um parâmetro que se chama pattern"}
    assert original == copia


def test_esquema_com_ref_vira_objeto_livre() -> None:
    com_ref = {"type": "object", "properties": {"a": {"$ref": "#/$defs/A"}}, "$defs": {"A": {"type": "string"}}}
    assert sanitize(com_ref) == {"type": "object"}


# --- leitura ------------------------------------------------------------------------------------------------------


def test_answer() -> None:
    assert parse_action('{"action": "answer"}') == AnswerAction()


def test_tool_com_argumentos() -> None:
    assert parse_action('{"action": "tool", "name": "generic.calculate", "arguments": {"expression": "2+2"}}') == (
        ToolAction(name="generic.calculate", arguments={"expression": "2+2"})
    )


def test_tool_sem_argumentos_vira_objeto_vazio() -> None:
    assert parse_action('{"action": "tool", "name": "crm.listar"}') == ToolAction(name="crm.listar", arguments={})
    assert parse_action('{"action": "tool", "name": "crm.listar", "arguments": null}') == ToolAction(
        name="crm.listar", arguments={}
    )


def test_nome_fora_de_qualquer_catalogo_ainda_e_tool() -> None:
    """Quem diz "tool inexistente" é o gateway (004 FR-005), não o motor (R18)."""
    assert isinstance(parse_action('{"action": "tool", "name": "x.nao_existe", "arguments": {}}'), ToolAction)


def test_nome_nao_e_aparado() -> None:
    action = parse_action('{"action": "tool", "name": " generic.calculate", "arguments": {}}')
    assert isinstance(action, ToolAction) and action.name == " generic.calculate"


@pytest.mark.parametrize(
    "content",
    [
        None,
        "",
        "   ",
        "isso não é json",
        '{"action": "tool", "name": "a.b", "arguments": {}',
        "[1, 2]",
        "42",
        '"answer"',
        "{}",
        '{"action": "pensar"}',
        '{"action": "tool"}',
        '{"action": "tool", "name": ""}',
        '{"action": "tool", "name": "  "}',
        '{"action": "tool", "name": 7}',
        '{"action": "tool", "name": "a.b", "arguments": [1]}',
        '{"action": "tool", "name": "a.b", "arguments": "{}"}',
    ],
)
def test_saidas_que_nao_sao_acao(content: str | None) -> None:
    action = parse_action(content)
    assert isinstance(action, InvalidAction)
    assert action.reason in INVALID_REASONS


@given(st.text(max_size=300))
def test_texto_arbitrario_nunca_levanta_e_o_motivo_nao_copia_a_saida(content: str) -> None:
    action = parse_action(content)
    if isinstance(action, InvalidAction):
        assert action.reason in INVALID_REASONS


@given(
    st.recursive(
        st.none() | st.booleans() | st.integers() | st.text(max_size=20),
        lambda children: st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=10), children, max_size=4),
        max_leaves=20,
    )
)
def test_json_arbitrario_nunca_levanta(value: Any) -> None:
    action = parse_action(json.dumps(value))
    assert isinstance(action, ToolAction | AnswerAction | InvalidAction)
