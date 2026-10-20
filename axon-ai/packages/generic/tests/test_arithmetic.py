"""Aritmética pura do pack genérico (spec 010, T005): casos válidos, recusas com mensagem exata e limites.

Sem `pytest-asyncio`: no ambiente limpo (quickstart §5) só existe `pytest`.
"""

from __future__ import annotations

import pytest

from axon_generic.tools.arithmetic import (
    DIVISION_BY_ZERO,
    EXPONENT_OUT_OF_RANGE,
    INVALID,
    MAX_LENGTH,
    NOT_ARITHMETIC,
    OUT_OF_DOMAIN,
    TOO_LONG,
    ExpressionError,
    evaluate,
    normalize,
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("10 / 4", 2.5),
        ("7 // 2", 3),
        ("7 % 3", 1),
        ("2 ** 10", 1024),
        ("-3 ** 2", -9),
        ("+3 - -3", 6),
        ("1.5 * 2", 3.0),
        ("2 ** 0.5", 2**0.5),
        ("2 ** 1000", 2**1000),
    ],
)
def test_valid_expressions(expression: str, expected: float) -> None:
    assert evaluate(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "x + 1",
        "pi",
        "__import__('os').system('id')",
        "open('/etc/passwd').read()",
        "(1).__class__",
        "[1, 2][0]",
        "1 < 2",
        "1 and 2",
        "f'{1}'",
        "[i for i in (1, 2)]",
        "(y := 2)",
        "True + 1",
        "'a' * 3",
        "1 if 1 else 2",
        "lambda: 1",
    ],
)
def test_only_arithmetic_is_allowed(expression: str) -> None:
    with pytest.raises(ExpressionError, match=NOT_ARITHMETIC):
        evaluate(expression)


@pytest.mark.parametrize("expression", ["1/0", "5 % 0", "7 // 0", "1 / 0.0"])
def test_division_by_zero(expression: str) -> None:
    with pytest.raises(ExpressionError, match=DIVISION_BY_ZERO):
        evaluate(expression)


@pytest.mark.parametrize("expression", ["1 +", "((1)", "", "2 +* 3"])
def test_syntax_error(expression: str) -> None:
    with pytest.raises(ExpressionError, match=INVALID):
        evaluate(expression)


def test_length_limit() -> None:
    accepted = "1+" * ((MAX_LENGTH - 1) // 2) + "1"
    assert len(accepted) <= MAX_LENGTH
    assert evaluate(accepted) == (MAX_LENGTH + 1) // 2
    with pytest.raises(ExpressionError, match=TOO_LONG):
        evaluate("1+" * MAX_LENGTH + "1")


@pytest.mark.parametrize("expression", ["2 ** 10**9", "2 ** 1001", "(2**1000) ** 1000", "2 ** -2000"])
def test_exponent_limit(expression: str) -> None:
    with pytest.raises(ExpressionError, match=EXPONENT_OUT_OF_RANGE):
        evaluate(expression)


@pytest.mark.parametrize("expression", ["1e308 * 10", "1e308 + 1e308", "10.0 ** 400"])
def test_result_out_of_domain(expression: str) -> None:
    with pytest.raises(ExpressionError, match=OUT_OF_DOMAIN):
        evaluate(expression)


def test_normalize_strips_and_evaluate_ignores_surrounding_space() -> None:
    assert normalize("  2 + 2  ") == "2 + 2"
    assert evaluate("  2 + 2  ") == 4


def test_is_deterministic() -> None:
    assert evaluate("6 * 7") == evaluate("6 * 7") == 42
