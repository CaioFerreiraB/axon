"""Montagem do evento final: pura, sem I/O (US1 cenário 3).

O validator pode alterar a resposta e as citações — quando altera, é a versão dele que o consumidor recebe, e o que
ele apontou vira erro registrado. Validator que reprova **não** transforma a execução em falha: a resposta sai com a
marcação, que é o que o princípio IX pede (fonte não vigente citada é marcada, não escondida).
"""

from __future__ import annotations

from collections.abc import Sequence

from axon_ai.graph.api import ExecutionIssue, FinalEvent
from axon_ai.packs.api import ValidationOutcome

VALIDATION_STAGE = "validate_answer"
VALIDATOR_ISSUE = "ValidatorIssue"


def final_event(
    *,
    generated: str,
    outcome: ValidationOutcome | None,
    errors: Sequence[ExecutionIssue] = (),
) -> FinalEvent:
    """Junta a resposta gerada, o resultado dos validators e os erros acumulados num único evento final."""
    if outcome is None:
        return FinalEvent(answer=generated, errors=tuple(errors))
    return FinalEvent(
        answer=outcome.answer if outcome.answer is not None else generated,
        citations=tuple(outcome.citations),
        errors=(*errors, *_issues(outcome)),
        flags=outcome.flags,
    )


def succeeded(final: FinalEvent) -> bool:
    """A execução deu certo quando nenhum registro tem gravidade `error` (ADR-018, research R23).

    Validator que reprova é achado sobre a resposta, não falha de execução — por isso sai como `notice`, como os
    resultados de política do loop (limite, ação inválida, teto de contexto). Decidir pelo `kind` acoplaria quem
    consome a cada nome novo.
    """
    return all(issue.severity == "notice" for issue in final.errors)


def _issues(outcome: ValidationOutcome) -> tuple[ExecutionIssue, ...]:
    """Uma entrada por apontamento de validator, nomeando o pack e o validator que apontou."""
    return tuple(
        ExecutionIssue(
            stage=VALIDATION_STAGE,
            kind=VALIDATOR_ISSUE,
            message=f"{run.pack}.{run.validator}: {issue}",
            severity="notice",
        )
        for run in outcome.runs
        for issue in run.result.issues
    )
