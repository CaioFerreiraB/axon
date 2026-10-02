"""T010 — montagem do evento final (`domain/outcome.py`), a regra da US1 cenário 3."""

from __future__ import annotations

import pytest
from graph_testkit import outcome

from ai_core.graph.api import ExecutionIssue, FinalEvent
from ai_core.graph.domain.outcome import final_event, succeeded

CITATION = {"chunk_id": "c1", "document": "doc"}


def test_sem_validators_a_resposta_gerada_passa_inteira() -> None:
    final = final_event(generated="Brasília", outcome=None)
    assert final.answer == "Brasília"
    assert final.citations == ()
    assert final.errors == ()


def test_validator_que_nao_altera_preserva_a_resposta() -> None:
    final = final_event(generated="Brasília", outcome=outcome())
    assert final.answer == "Brasília"


def test_validator_que_altera_resposta_e_citacoes_prevalece() -> None:
    final = final_event(
        generated="Brasília com fonte inventada",
        outcome=outcome(answer="Brasília", citations=[CITATION]),  # type: ignore[list-item]
    )
    assert final.answer == "Brasília"
    assert final.citations == (CITATION,)


def test_cada_apontamento_vira_um_erro_registrado() -> None:
    final = final_event(generated="x", outcome=outcome(ok=False, issues=["citação removida", "sem fonte"]))
    assert [issue.kind for issue in final.errors] == ["ValidatorIssue", "ValidatorIssue"]
    assert "citação removida" in final.errors[0].message
    assert "generic.checa" in final.errors[0].message


def test_marcacoes_do_validator_chegam_ao_evento_final() -> None:
    final = final_event(generated="x", outcome=outcome(flags=frozenset({"nao_fundamentada"})))
    assert final.flags == frozenset({"nao_fundamentada"})


def test_erros_anteriores_sao_preservados_antes_dos_apontamentos() -> None:
    anterior = ExecutionIssue(stage="prepare_context", kind="Aviso", message="fatia truncada")
    final = final_event(generated="x", outcome=outcome(issues=["sem fonte"]), errors=[anterior])
    assert final.errors[0] is anterior
    assert final.errors[1].kind == "ValidatorIssue"


def test_validator_que_reprova_nao_torna_a_execucao_falha() -> None:
    """Reprovar é achado sobre a resposta; a resposta sai com a marcação (princípio IX)."""
    final = final_event(generated="x", outcome=outcome(ok=False, issues=["sem fonte"]))
    assert succeeded(final) is True


def test_erro_de_execucao_torna_a_execucao_falha() -> None:
    final = final_event(
        generated="x",
        outcome=None,
        errors=[ExecutionIssue(stage="generate", kind="ModelCallFailed", message="provider caiu")],
    )
    assert succeeded(final) is False


# --- Fase 3 (T030; research R23, ADR-018) ----------------------------------------------------------------------------


@pytest.mark.us2
def test_apontamento_de_validator_sai_como_aviso() -> None:
    final = final_event(generated="x", outcome=outcome(ok=False, issues=("sem citação",)))
    (issue,) = final.errors
    assert issue.kind == "ValidatorIssue"
    assert issue.severity == "notice"


@pytest.mark.us2
def test_sucesso_e_decidido_pela_gravidade_e_nao_pelo_kind() -> None:
    aviso = ExecutionIssue(stage="controller", kind="IterationLimit", message="limite 3", severity="notice")
    falha = ExecutionIssue(stage="controller", kind="ModelCallFailed", message="ctrl/x: fora do ar")
    assert succeeded(FinalEvent(answer="x", errors=(aviso,)))
    assert not succeeded(FinalEvent(answer="x", errors=(aviso, falha)))
    sem_gravidade = ExecutionIssue(stage="s", kind="ValidatorIssue", message="m")
    assert not succeeded(FinalEvent(answer="x", errors=(sem_gravidade,)))
