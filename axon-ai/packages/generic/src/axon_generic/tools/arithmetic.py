"""Aritmética determinística sobre uma expressão de texto (spec 010, research R6).

A expressão vem do modelo, logo é conteúdo não-confiável (princípio VI): nada de `eval`. O texto é analisado como AST
e só uma allowlist de nós e de operadores é avaliada, com limites de tamanho e de magnitude. Módulo puro — sem I/O,
sem relógio, sem aleatoriedade.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping
from typing import Final

from axon_ai_contracts import JSONValue, ToolInvocation, ToolSpec

MAX_LENGTH: Final = 200
"""Tamanho máximo da expressão, já normalizada (data-model.md)."""

MAX_EXPONENT: Final = 1000
"""Magnitude máxima do expoente em `**` (data-model.md)."""

MAX_RESULT_BITS: Final = 4096
"""Magnitude máxima estimada do resultado de `**`, em bits: barra `(2**1000)**1000` sem barrar `2**1000`."""

INVALID: Final = "expressão inválida"
NOT_ARITHMETIC: Final = "expressão inválida: só aritmética com números é permitida"
DIVISION_BY_ZERO: Final = "divisão por zero"
TOO_LONG: Final = "expressão longa demais"
EXPONENT_OUT_OF_RANGE: Final = "expoente fora do limite"
OUT_OF_DOMAIN: Final = "resultado fora do domínio"
NOT_A_STRING: Final = "expression precisa ser uma string"

PARAMETERS: Final[Mapping[str, JSONValue]] = {
    "type": "object",
    "properties": {"expression": {"type": "string"}},
    "required": ["expression"],
    "additionalProperties": False,
}


class ExpressionError(Exception):
    """Expressão recusada. A mensagem é o texto que o handler devolve em `error` (contracts/generic-pack.md)."""


type _Number = int | float


def normalize(expression: str) -> str:
    """Forma canônica da expressão: sem espaços nas extremidades. É o valor ecoado em `expression`."""
    return expression.strip()


def _number(value: object) -> _Number:
    # bool é subclasse de int: `True + 1` não é aritmética com números.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ExpressionError(NOT_ARITHMETIC)
    return value


def _bits(value: _Number) -> int:
    if isinstance(value, int):
        return max(value.bit_length(), 1)
    if value == 0 or not math.isfinite(value):
        return 1
    return max(int(math.log2(abs(value))) + 1, 1)


def _power(left: _Number, right: _Number) -> _Number:
    if abs(right) > MAX_EXPONENT or _bits(left) * abs(right) > MAX_RESULT_BITS:
        raise ExpressionError(EXPONENT_OUT_OF_RANGE)
    return left**right


def _divide(left: _Number, right: _Number, operator: ast.operator) -> _Number:
    if right == 0:
        raise ExpressionError(DIVISION_BY_ZERO)
    if isinstance(operator, ast.Div):
        return left / right
    if isinstance(operator, ast.FloorDiv):
        return left // right
    return left % right


def _binary(node: ast.BinOp) -> _Number:
    left, right = _evaluate_node(node.left), _evaluate_node(node.right)
    operator = node.op
    if isinstance(operator, ast.Add):
        return left + right
    if isinstance(operator, ast.Sub):
        return left - right
    if isinstance(operator, ast.Mult):
        return left * right
    if isinstance(operator, ast.Div | ast.FloorDiv | ast.Mod):
        return _divide(left, right, operator)
    if isinstance(operator, ast.Pow):
        return _power(left, right)
    raise ExpressionError(NOT_ARITHMETIC)


def _unary(node: ast.UnaryOp) -> _Number:
    operand = _evaluate_node(node.operand)
    if isinstance(node.op, ast.UAdd):
        return +operand
    if isinstance(node.op, ast.USub):
        return -operand
    raise ExpressionError(NOT_ARITHMETIC)


def _evaluate_node(node: ast.expr) -> _Number:
    """Allowlist: constante numérica, operação binária e operação unária. Qualquer outro nó é recusado."""
    if isinstance(node, ast.Constant):
        return _number(node.value)
    if isinstance(node, ast.BinOp):
        return _binary(node)
    if isinstance(node, ast.UnaryOp):
        return _unary(node)
    raise ExpressionError(NOT_ARITHMETIC)


def evaluate(expression: str) -> _Number:
    """Valor da expressão aritmética. Levanta `ExpressionError` em qualquer recusa — nunca executa nada."""
    if len(normalize(expression)) > MAX_LENGTH:
        raise ExpressionError(TOO_LONG)
    try:
        tree = ast.parse(normalize(expression), mode="eval")
    except (SyntaxError, ValueError, MemoryError, RecursionError) as error:
        raise ExpressionError(INVALID) from error
    try:
        result = _evaluate_node(tree.body)
    except OverflowError as error:
        raise ExpressionError(OUT_OF_DOMAIN) from error
    if isinstance(result, float) and not math.isfinite(result):
        raise ExpressionError(OUT_OF_DOMAIN)
    return result


async def calculate(invocation: ToolInvocation) -> Mapping[str, JSONValue]:
    """Handler nativo da tool `calculate`: nunca levanta — toda recusa vira `{"error": ...}`.

    Não usa `request_id` nem `reference_time`: o resultado depende só da expressão.
    """
    expression = invocation.arguments.get("expression")
    if not isinstance(expression, str):
        return {"error": NOT_A_STRING}
    try:
        return {"expression": normalize(expression), "result": evaluate(expression)}
    except ExpressionError as error:
        return {"error": str(error)}


def calculate_spec() -> ToolSpec:
    """Especificação da tool nativa (contracts/generic-pack.md). O core aplica o namespace `generic.calculate`."""
    return ToolSpec(
        name="calculate",
        description="Calcula uma expressão aritmética com números.",
        parameters=PARAMETERS,
        kind="native",
        mutates=False,
        handler=calculate,
    )
