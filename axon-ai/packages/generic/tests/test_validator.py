"""Validator `non_empty_answer` (spec 010, T006): as três linhas da tabela de data-model.md."""

from __future__ import annotations

import asyncio

import pytest

from axon_ai_contracts.testing import turn_view, validator_context
from axon_generic.validators.answer import NonEmptyAnswer


def _validate(answer: str | None) -> object:
    validator = NonEmptyAnswer()
    return asyncio.run(validator.validate(turn_view(answer=answer), validator_context("generic")))


def test_name() -> None:
    assert NonEmptyAnswer().name == "non_empty_answer"


def test_answer_with_content_is_approved() -> None:
    result = _validate("Resposta com conteúdo.")
    assert (result.ok, result.issues, result.flags) == (True, (), frozenset())
    assert result.answer is None and result.citations is None


@pytest.mark.parametrize("answer", [None, "", "   ", "\n\t "])
def test_empty_answer_is_rejected(answer: str | None) -> None:
    result = _validate(answer)
    assert (result.ok, result.issues, result.flags) == (False, ("resposta vazia",), frozenset({"empty_answer"}))
    assert result.answer is None and result.citations is None


def test_is_deterministic() -> None:
    validator = NonEmptyAnswer()
    view, ctx = turn_view(answer=" "), validator_context("generic")
    assert asyncio.run(validator.validate(view, ctx)) == asyncio.run(validator.validate(view, ctx))
