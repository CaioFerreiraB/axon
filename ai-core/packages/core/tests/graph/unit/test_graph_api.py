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
        "ExecutionEngine",
        "ExecutionEvent",
        "ExecutionGrant",
        "ExecutionIssue",
        "ExecutionRequest",
        "FinalEvent",
        "ProgressEvent",
        "TokenEvent",
        "ExecutionError",
        "ExecutionRequestInvalid",
        "UnknownFlow",
        "FLOW_CHAT",
        "FLOW_AGENTIC",
        "IssueSeverity",
    }
    assert expected <= public
    assert not getattr(graph_api.ExecutionGrant, "_is_protocol", False)


# --- Fase 5 (T064; research R44; data-model "Fase 5") ----------------------------------------------------------------


@pytest.mark.us3
def test_nome_do_flow_rag_first_e_nomes_publicos() -> None:
    assert graph_api.FLOW_RAG_FIRST == "rag_first"
    public = {name for name in vars(graph_api) if not name.startswith("_")}
    assert {"FLOW_RAG_FIRST", "RagSettings"} <= public
    assert {"FLOW_RAG_FIRST", "RagSettings"} <= set(graph_api.__all__)


@pytest.mark.us3
def test_numeros_do_rag_first_por_default() -> None:
    settings = graph_api.RagSettings()
    assert (settings.candidates, settings.passages, settings.min_score) == (20, 5, None)


@pytest.mark.us3
@pytest.mark.parametrize(
    ("fields", "named"),
    [
        ({"candidates": 0}, "candidates"),
        ({"passages": 0}, "passages"),
        ({"candidates": True}, "candidates"),
        ({"passages": 2.0}, "passages"),
        ({"min_score": -0.01}, "min_score"),
        ({"min_score": 1.01}, "min_score"),
        ({"min_score": float("nan")}, "min_score"),
    ],
)
def test_numeros_invalidos_sao_recusados_nomeando_o_campo(fields: dict[str, object], named: str) -> None:
    with pytest.raises(ValueError, match=named):
        graph_api.RagSettings(**fields)  # type: ignore[arg-type]


@pytest.mark.us3
@pytest.mark.parametrize("min_score", [0.0, 1.0, 0.5])
def test_limiar_nas_bordas_e_aceito(min_score: float) -> None:
    assert graph_api.RagSettings(min_score=min_score).min_score == min_score


# --- Desfecho de etapa (ADR-028) -----------------------------------------------------------------------------------


def test_nomes_publicos_do_desfecho_de_etapa() -> None:
    public = {name for name in vars(graph_api) if not name.startswith("_")}
    assert {
        "StepFinished",
        "StepOutcome",
        "SourceRef",
        "ToolCallSummary",
        "ToolCallsOutcome",
        "RerankOutcome",
        "GateOutcome",
        "GateRoute",
        "ControllerOutcome",
        "ControllerAction",
        "GenerationOutcome",
        "CatalogOutcome",
    } <= public


def test_fim_de_etapa_exige_etapa_e_aceita_desfecho_vazio() -> None:
    assert graph_api.StepFinished(stage="validate_answer").outcome is None
    with pytest.raises(ValueError):
        graph_api.StepFinished(stage=" ")


def test_argumentos_da_chamada_sao_congelados() -> None:
    arguments = {"query": "x"}
    summary = graph_api.ToolCallSummary(tool="docs.search", arguments=arguments, status="ok")
    arguments["query"] = "mudou"
    assert summary.arguments == {"query": "x"}
    with pytest.raises(TypeError):
        summary.arguments["query"] = "y"  # type: ignore[index]


@pytest.mark.parametrize(
    "build",
    [
        lambda: graph_api.SourceRef(document=""),
        lambda: graph_api.ToolCallSummary(tool="", status="ok"),
        lambda: graph_api.RerankOutcome(candidates=-1),
        lambda: graph_api.GateOutcome(covered=True, route="outro"),  # type: ignore[arg-type]
        lambda: graph_api.GateOutcome(covered=True, route="generate", delivered=-1),
        lambda: graph_api.ControllerOutcome(iteration=0, action="answer", model="p/m"),
        lambda: graph_api.ControllerOutcome(iteration=1, action="limit", model="p/m"),  # type: ignore[arg-type]
        lambda: graph_api.GenerationOutcome(model=" "),
        lambda: graph_api.GenerationOutcome(model="p/m", output_tokens=-2),
        lambda: graph_api.CatalogOutcome(tools=-1),
    ],
)
def test_desfecho_invalido_e_recusado_na_construcao(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # type: ignore[operator]
