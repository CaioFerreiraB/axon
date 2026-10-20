"""Validação determinística da resposta (spec 010, T011).

Checagem mecânica, no caminho da requisição: julgamento por LLM pertence só ao harness offline (ADR-007).
"""

from __future__ import annotations

from typing import Final

from axon_ai_contracts import TurnView, ValidationResult, ValidatorContext

EMPTY_ANSWER: Final = "empty_answer"
EMPTY_ANSWER_ISSUE: Final = "resposta vazia"


class NonEmptyAnswer:
    """Reprova resposta ausente, vazia ou só de espaços. Não reescreve `answer` nem `citations`."""

    name = "non_empty_answer"

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        if view.answer is not None and view.answer.strip():
            return ValidationResult(ok=True)
        return ValidationResult(ok=False, issues=(EMPTY_ANSWER_ISSUE,), flags=frozenset({EMPTY_ANSWER}))
