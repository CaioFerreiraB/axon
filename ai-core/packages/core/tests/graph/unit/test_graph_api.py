"""T008 — tipos publicados do seam (data-model.md)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from graph_testkit import MESSAGES, REQUEST_ID

import ai_core.assistants.api as assistants_api
import ai_core.graph.api as graph_api
from ai_core.graph.api import (
    FLOW_AGENTIC,
    FLOW_CHAT,
    ExecutionError,
    ExecutionIssue,
    ExecutionRequest,
    ExecutionRequestInvalid,
    FinalEvent,
    ProgressEvent,
    TokenEvent,
    UnknownFlow,
)


def test_requisicao_minima() -> None:
    request = ExecutionRequest(request_id=REQUEST_ID, messages=MESSAGES)
    assert request.stream is True
    assert request.reference_time is None


def test_requisicao_sem_mensagens_e_rejeitada() -> None:
    with pytest.raises(ValueError):
        ExecutionRequest(request_id=REQUEST_ID, messages=())


def test_requisicao_sem_identificador_e_rejeitada() -> None:
    with pytest.raises(ValueError):
        ExecutionRequest(request_id="  ", messages=MESSAGES)


def test_data_de_referencia_exige_timezone() -> None:
    """ADR-013: sem timezone, o conjunto dourado da 105 não seria reproduzível."""
    with pytest.raises(ValueError, match="timezone"):
        ExecutionRequest(request_id=REQUEST_ID, messages=MESSAGES, reference_time=datetime(2026, 9, 21))


def test_data_de_referencia_com_timezone_e_aceita() -> None:
    at = datetime(2026, 9, 21, tzinfo=UTC)
    assert ExecutionRequest(request_id=REQUEST_ID, messages=MESSAGES, reference_time=at).reference_time == at


def test_progresso_exige_etapa() -> None:
    with pytest.raises(ValueError):
        ProgressEvent(stage="")


def test_erro_exige_etapa_e_classe() -> None:
    with pytest.raises(ValueError):
        ExecutionIssue(stage="generate", kind=" ", message="x")


def test_evento_final_congela_colecoes() -> None:
    final = FinalEvent(answer="oi", citations=[], errors=[], flags={"marca"})
    assert final.citations == ()
    assert final.errors == ()
    assert final.flags == frozenset({"marca"})


def test_token_carrega_o_pedaco() -> None:
    assert TokenEvent(text="Bras").text == "Bras"


def test_hierarquia_de_erro() -> None:
    """A 008 trata uma hierarquia só, e `UnknownFlow` é um caso de requisição inválida."""
    assert issubclass(ExecutionRequestInvalid, ExecutionError)
    assert issubclass(UnknownFlow, ExecutionRequestInvalid)
    assert not issubclass(ExecutionRequestInvalid, ValueError)


# --- Fase 3 (T028; research R15, R16, R23; ADR-018) -----------------------------------------------------------------


@pytest.mark.us2
def test_nome_do_flow_agentic() -> None:
    assert FLOW_AGENTIC == "agentic"
    assert FLOW_CHAT == "chat"


@pytest.mark.us2
def test_registro_e_erro_por_default() -> None:
    issue = ExecutionIssue(stage="generate", kind="ModelCallFailed", message="x")
    assert issue.severity == "error"


@pytest.mark.us2
def test_registro_aceita_aviso() -> None:
    issue = ExecutionIssue(stage="controller", kind="IterationLimit", message="x", severity="notice")
    assert issue.severity == "notice"


@pytest.mark.us2
def test_gravidade_fora_do_vocabulario_e_recusada() -> None:
    with pytest.raises(ValueError, match="severity"):
        ExecutionIssue(stage="controller", kind="X", message="x", severity="warning")  # type: ignore[arg-type]


@pytest.mark.us2
def test_o_grant_do_motor_e_o_da_003() -> None:
    """A ponte do R3 terminou: o seam recebe o value object da 003, reexportado com o mesmo nome (ADR-018)."""
    assert graph_api.ExecutionGrant is assistants_api.ExecutionGrant


@pytest.mark.us2
def test_nomes_publicos_do_seam() -> None:
    public = {name for name in vars(graph_api) if not name.startswith("_")}
    expected = {
        "ExecutionEngine", "ExecutionEvent", "ExecutionGrant", "ExecutionIssue", "ExecutionRequest", "FinalEvent",
        "ProgressEvent", "TokenEvent", "ExecutionError", "ExecutionRequestInvalid", "UnknownFlow", "FLOW_CHAT",
        "FLOW_AGENTIC", "IssueSeverity",
    }
    assert expected <= public
    assert not getattr(graph_api.ExecutionGrant, "_is_protocol", False)
