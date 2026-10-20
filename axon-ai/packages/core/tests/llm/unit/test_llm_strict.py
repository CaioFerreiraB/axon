"""Subconjunto estrito da OpenAI: conversão e inversa, puras (spec 006 FR-005; ADR-023; research R27, R28; T055)."""

from __future__ import annotations

import copy
from typing import Any

import jsonschema
import pytest

from axon_ai.capabilities.api import CatalogTool
from axon_ai.graph.domain.actions import action_schema
from axon_ai.llm.domain.strict import StrictSchemaError, from_strict, to_strict

pytestmark = pytest.mark.us4

FERRAMENTA = {
    "type": "object",
    "properties": {"cidade": {"type": "string"}, "dias": {"type": "integer"}},
    "required": ["cidade"],
}


# --- conversão ----------------------------------------------------------------------------------------------------


def test_objeto_ganha_additional_properties_e_opcional_vira_anulavel() -> None:
    plano = to_strict(FERRAMENTA)
    assert plano.wrapped is False
    assert plano.wire == {
        "type": "object",
        "properties": {"cidade": {"type": "string"}, "dias": {"type": ["integer", "null"]}},
        "required": ["cidade", "dias"],
        "additionalProperties": False,
    }


def test_raiz_any_of_e_embrulhada_em_value() -> None:
    esquema = {"anyOf": [{"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}]}
    plano = to_strict(esquema)
    assert plano.wrapped is True
    assert plano.wire["type"] == "object"
    assert plano.wire["required"] == ["value"]
    assert plano.wire["additionalProperties"] is False
    assert plano.wire["properties"]["value"]["anyOf"][0]["additionalProperties"] is False


@pytest.mark.parametrize(
    ("opcional", "anulavel"),
    [
        ({"type": "string"}, {"type": ["string", "null"]}),
        ({"type": ["string", "integer"]}, {"type": ["string", "integer", "null"]}),
        ({"type": "string", "enum": ["a", "b"]}, {"type": ["string", "null"], "enum": ["a", "b", None]}),
        ({"const": "x"}, {"anyOf": [{"const": "x", "type": "string"}, {"type": "null"}]}),
        (
            {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}]},
        ),
        ({"type": ["string", "null"]}, {"type": ["string", "null"]}),
    ],
    ids=["texto", "lista", "enum", "const", "anyOf", "ja-anulavel"],
)
def test_formas_de_anular(opcional: dict[str, Any], anulavel: dict[str, Any]) -> None:
    plano = to_strict({"type": "object", "properties": {"p": opcional}})
    assert plano.wire["properties"]["p"] == anulavel
    assert plano.wire["required"] == ["p"]


@pytest.mark.parametrize(
    ("no", "tipo"),
    [
        ({"const": "answer"}, "string"),
        ({"const": 3}, "integer"),
        ({"const": True}, "boolean"),
        ({"enum": ["a", "b"]}, "string"),
        ({"enum": ["a", 1]}, ["string", "integer"]),
    ],
)
def test_const_e_enum_ganham_type(no: dict[str, Any], tipo: Any) -> None:
    """O modo estrito exige `type` em todo nó — visto num 400 real da OpenAI no ramo `answer` da 005."""
    plano = to_strict({"type": "object", "properties": {"p": no}, "required": ["p"]})
    assert plano.wire["properties"]["p"]["type"] == tipo


def test_one_of_vira_any_of_e_anotacoes_saem() -> None:
    esquema = {
        "type": "object",
        "title": "Busca",
        "properties": {"q": {"oneOf": [{"type": "string"}, {"type": "integer"}], "default": "x", "examples": ["y"]}},
        "required": ["q"],
    }
    assert to_strict(esquema).wire == {
        "type": "object",
        "properties": {"q": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
        "required": ["q"],
        "additionalProperties": False,
    }


def test_defs_vao_para_a_nova_raiz() -> None:
    esquema = {
        "$defs": {"ponto": {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}},
        "anyOf": [{"$ref": "#/$defs/ponto"}],
    }
    plano = to_strict(esquema)
    assert plano.wrapped is True
    assert plano.wire["$defs"]["ponto"]["additionalProperties"] is False
    assert plano.wire["properties"]["value"] == {"anyOf": [{"$ref": "#/$defs/ponto"}]}


def test_o_esquema_recebido_nao_muda() -> None:
    original = copy.deepcopy(FERRAMENTA)
    to_strict(FERRAMENTA)
    assert original == FERRAMENTA


@pytest.mark.parametrize(
    ("esquema", "caminho", "motivo"),
    [
        ({"type": "object"}, "$", "objeto livre"),
        ({"type": "object", "properties": {"a": {"type": "object"}}}, "$.properties.a", "objeto livre"),
        ({"type": "object", "properties": {}, "additionalProperties": True}, "$", "additionalProperties"),
        ({"allOf": [{"type": "string"}]}, "$", "allOf"),
        ({"type": "object", "properties": {"a": {"type": "string", "if": {}}}}, "$.properties.a", "if"),
        ({"type": "object", "properties": {}, "patternProperties": {}}, "$", "patternProperties"),
        ({"type": "object", "properties": {"a": {}}}, "$.properties.a", "sem tipo"),
    ],
    ids=["raiz-livre", "aninhado-livre", "aberto", "allOf", "if", "patternProperties", "sem-tipo"],
)
def test_sem_equivalente_estrito_e_recusado_com_o_caminho(esquema: dict[str, Any], caminho: str, motivo: str) -> None:
    with pytest.raises(StrictSchemaError) as erro:
        to_strict(esquema)
    assert erro.value.path == caminho
    assert motivo in str(erro.value)


# --- inversa ------------------------------------------------------------------------------------------------------


def test_inversa_tira_o_null_introduzido() -> None:
    plano = to_strict(FERRAMENTA)
    assert from_strict({"cidade": "Recife", "dias": None}, plano) == {"cidade": "Recife"}
    assert from_strict({"cidade": "Recife", "dias": 3}, plano) == {"cidade": "Recife", "dias": 3}


def test_inversa_mantem_o_null_que_o_original_admitia() -> None:
    plano = to_strict({"type": "object", "properties": {"nota": {"type": ["string", "null"]}}})
    assert from_strict({"nota": None}, plano) == {"nota": None}


def test_inversa_desembrulha_value() -> None:
    plano = to_strict({"anyOf": [{"type": "object", "properties": {"a": {"type": "string"}}}]})
    assert from_strict({"value": {"a": None}}, plano) == {}


def test_inversa_escolhe_o_ramo_por_chaves_e_const() -> None:
    esquema = {
        "anyOf": [
            {"type": "object", "properties": {"k": {"const": "x"}, "n": {"type": "string"}}, "required": ["k"]},
            {"type": "object", "properties": {"k": {"const": "y"}, "m": {"type": "string"}}, "required": ["k", "m"]},
        ]
    }
    plano = to_strict(esquema)
    assert from_strict({"value": {"k": "x", "n": None}}, plano) == {"k": "x"}
    assert from_strict({"value": {"k": "y", "m": "z"}}, plano) == {"k": "y", "m": "z"}


def test_inversa_percorre_arrays() -> None:
    esquema = {"type": "object", "properties": {"itens": {"type": "array", "items": FERRAMENTA}}, "required": ["itens"]}
    plano = to_strict(esquema)
    valor = {"itens": [{"cidade": "A", "dias": None}, {"cidade": "B", "dias": 2}]}
    assert from_strict(valor, plano) == {"itens": [{"cidade": "A"}, {"cidade": "B", "dias": 2}]}


def test_inversa_devolve_como_veio_o_que_nao_casa() -> None:
    plano = to_strict({"anyOf": [{"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}]})
    assert from_strict({"outra": 1}, plano) == {"outra": 1}
    assert from_strict("texto", plano) == "texto"


# --- propriedade: o esquema de ação da 005 ida e volta ------------------------------------------------------------


def test_acao_da_005_desfeita_valida_contra_o_esquema_original() -> None:
    ferramenta = CatalogTool(name="clima.previsao", description="Previsão.", parameters=FERRAMENTA, kind="mcp")
    original = action_schema([ferramenta])
    plano = to_strict(original)

    assert plano.wrapped is True  # o anyOf da 005 na raiz
    estrito = {"value": {"action": "tool", "name": "clima.previsao", "arguments": {"cidade": "Natal", "dias": None}}}
    jsonschema.validate(estrito, plano.wire)
    desfeito = from_strict(estrito, plano)
    assert desfeito == {"action": "tool", "name": "clima.previsao", "arguments": {"cidade": "Natal"}}
    jsonschema.validate(desfeito, original)

    resposta = {"value": {"action": "answer"}}
    jsonschema.validate(resposta, plano.wire)
    assert from_strict(resposta, plano) == {"action": "answer"}
