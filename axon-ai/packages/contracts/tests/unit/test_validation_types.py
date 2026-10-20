from __future__ import annotations

import pytest

from axon_ai_contracts.validation import AnswerValidator, ValidationResult, ValidatorContext
from axon_ai_contracts.view import TurnView


class _Validator:
    name = "sempre_ok"

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        return ValidationResult(ok=True)


def test_validation_result_defaults_and_freezing() -> None:
    result = ValidationResult(ok=False, issues=["x"], citations=[{"chunk_id": "c"}], flags={"ungrounded"})
    assert result.issues == ("x",)
    assert result.citations is not None and result.citations[0]["chunk_id"] == "c"
    assert result.flags == frozenset({"ungrounded"})
    assert ValidationResult(ok=True).citations is None


def test_validator_context_freezes_config() -> None:
    ctx = ValidatorContext(pack_name="p", config={"k": [1]})
    assert ctx.config == {"k": (1,)}
    with pytest.raises(ValueError):
        ValidatorContext(pack_name="")


def test_answer_validator_is_runtime_checkable() -> None:
    assert isinstance(_Validator(), AnswerValidator)
