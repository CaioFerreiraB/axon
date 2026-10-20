"""T008 — construção dos chunks no formato OpenAI (contracts/sse-format.md), pura."""

from __future__ import annotations

import pytest
from http_testkit import CREATED, MODEL_ID

from axon_ai.graph.api import ExecutionIssue, FinalEvent, ProgressEvent, TokenEvent
from axon_ai.http.domain.openai_chunks import (
    completion,
    final_chunk,
    finish_reason,
    opening_chunk,
    progress_chunk,
    queue_chunk,
    token_chunk,
)

ENVELOPE = {"request_id": "req-1", "model": MODEL_ID, "created": CREATED}
CITATION = {"chunk_id": "c1", "document": "doc"}


def test_primeiro_chunk_traz_o_papel_e_nenhum_conteudo() -> None:
    chunk = opening_chunk(**ENVELOPE)
    assert chunk["choices"][0]["delta"] == {"role": "assistant"}
    assert chunk["choices"][0]["finish_reason"] is None


def test_token_vira_chunk_com_o_pedaco() -> None:
    chunk = token_chunk(TokenEvent(text="Bras"), **ENVELOPE)
    assert chunk["choices"][0]["delta"] == {"content": "Bras"}
    assert chunk["choices"][0]["finish_reason"] is None
    assert "x_ai_core" not in chunk


def test_progresso_antes_do_texto_vai_como_raciocinio_e_campo_extra() -> None:
    """Fase 7 (R34): até o primeiro token, a linha em português em `reasoning_content`, terminada em quebra."""
    chunk = progress_chunk(ProgressEvent(stage="generate"), **ENVELOPE)
    assert chunk["choices"][0]["delta"] == {"reasoning_content": "Escrevendo a resposta…\n"}
    assert chunk["choices"][0]["finish_reason"] is None
    assert chunk["x_ai_core"]["progress"] == {"stage": "generate"}


def test_progresso_depois_do_texto_vai_com_delta_vazio_e_campo_extra() -> None:
    chunk = progress_chunk(ProgressEvent(stage="validate_answer"), reasoning=False, **ENVELOPE)
    assert chunk["choices"][0]["delta"] == {}
    assert chunk["x_ai_core"]["progress"] == {"stage": "validate_answer"}


def test_tool_nomeada_no_raciocinio() -> None:
    chunk = progress_chunk(ProgressEvent(stage="execute_tool", detail="generic.calculate"), **ENVELOPE)
    assert chunk["choices"][0]["delta"] == {"reasoning_content": "Usando a ferramenta generic.calculate…\n"}
    assert chunk["x_ai_core"]["progress"] == {"stage": "execute_tool", "detail": "generic.calculate"}


def test_chunk_da_fila() -> None:
    chunk = queue_chunk(position=2, **ENVELOPE)
    assert chunk["choices"][0]["delta"] == {"reasoning_content": "Aguardando uma vaga (posição 2 na fila)…\n"}
    assert chunk["choices"][0]["finish_reason"] is None
    assert chunk["x_ai_core"]["progress"] == {"stage": "queue", "detail": "2"}


def test_espera_esgotada_na_fila_e_desfecho_de_erro() -> None:
    issue = ExecutionIssue(stage="admission", kind="QueueTimeout", message="espera esgotada na fila")
    chunk = final_chunk(FinalEvent(answer="", errors=(issue,)), **ENVELOPE)
    assert chunk["choices"][0]["finish_reason"] == "error"
    assert chunk["x_ai_core"]["errors"] == [{"stage": "admission", "kind": "QueueTimeout", "message": issue.message}]


def test_progresso_com_detalhe() -> None:
    chunk = progress_chunk(ProgressEvent(stage="generate", detail="modelo local"), **ENVELOPE)
    assert chunk["x_ai_core"]["progress"]["detail"] == "modelo local"


def test_chunk_final_traz_desfecho_citacoes_e_marcacoes() -> None:
    final = FinalEvent(
        answer="Brasília",
        citations=(CITATION,),  # type: ignore[arg-type]
        flags=frozenset({"revisada"}),
    )
    chunk = final_chunk(final, **ENVELOPE)
    assert chunk["choices"][0]["finish_reason"] == "stop"
    assert chunk["x_ai_core"]["citations"] == [CITATION]
    assert chunk["x_ai_core"]["flags"] == ["revisada"]
    assert chunk["x_ai_core"]["request_id"] == "req-1"


def test_erro_de_execucao_vira_desfecho_de_erro() -> None:
    final = FinalEvent(
        answer="Bras",
        errors=(ExecutionIssue(stage="generate", kind="ModelCallFailed", message="provider caiu"),),
    )
    chunk = final_chunk(final, **ENVELOPE)
    assert chunk["choices"][0]["finish_reason"] == "error"
    assert chunk["x_ai_core"]["errors"][0]["kind"] == "ModelCallFailed"


def test_apontamento_de_validator_nao_vira_erro() -> None:
    """Reprovar é achado sobre a resposta, não falha de execução: o motor o registra como `notice` (ADR-018)."""
    aviso = ExecutionIssue(stage="validate_answer", kind="ValidatorIssue", message="sem fonte", severity="notice")
    final = FinalEvent(answer="Brasília", errors=(aviso,))
    assert final_chunk(final, **ENVELOPE)["choices"][0]["finish_reason"] == "stop"


# --- Fase 3 (T045; FR-022, ADR-018): o desfecho é da gravidade, não do tipo ------------------------------------------


@pytest.mark.parametrize("kind", ["IterationLimit", "ContextTrimmed", "InvalidAction", "ValidatorIssue", "Qualquer"])
def test_so_avisos_de_qualquer_tipo_sao_sucesso(kind: str) -> None:
    final = FinalEvent(answer="x", errors=(ExecutionIssue(stage="s", kind=kind, message="m", severity="notice"),))
    assert finish_reason(final) == "stop"


@pytest.mark.parametrize("kind", ["ModelCallFailed", "McpUnavailable", "ValidatorIssue"])
def test_um_erro_de_qualquer_tipo_e_falha(kind: str) -> None:
    aviso = ExecutionIssue(stage="s", kind="IterationLimit", message="m", severity="notice")
    erro = ExecutionIssue(stage="s", kind=kind, message="m", severity="error")
    assert finish_reason(FinalEvent(answer="x", errors=(aviso, erro))) == "error"


def test_sem_registros_e_sucesso() -> None:
    assert finish_reason(FinalEvent(answer="x")) == "stop"


def test_resposta_sem_streaming_traz_a_mensagem_inteira() -> None:
    final = FinalEvent(answer="Brasília", flags=frozenset({"revisada"}))
    body = completion(final, **ENVELOPE)
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"] == {"role": "assistant", "content": "Brasília"}
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["x_ai_core"]["flags"] == ["revisada"]


def test_envelope_e_igual_em_todos_os_chunks() -> None:
    final = FinalEvent(answer="Brasília")
    produzidos = [
        opening_chunk(**ENVELOPE),
        token_chunk(TokenEvent(text="Bras"), **ENVELOPE),
        progress_chunk(ProgressEvent(stage="generate"), **ENVELOPE),
        final_chunk(final, **ENVELOPE),
    ]
    for chunk in produzidos:
        assert chunk["id"] == "chatcmpl-req-1"
        assert chunk["object"] == "chat.completion.chunk"
        assert chunk["created"] == int(CREATED.timestamp())
        assert chunk["model"] == MODEL_ID


@pytest.mark.us6
def test_status_da_timeline_vai_na_chave_event_com_delta_vazio() -> None:
    """FR-005a (R42): o Open WebUI v0.12 repassa `event` ao emissor dele; o cliente padrão vê um chunk vazio."""
    from axon_ai.http.domain.openai_chunks import status_chunk
    from axon_ai.http.domain.timeline import Status

    started = status_chunk(Status("Escrevendo a resposta…", done=False), progress={"stage": "generate"}, **ENVELOPE)
    assert started["choices"][0]["delta"] == {}
    assert started["event"] == {"type": "status", "data": {"description": "Escrevendo a resposta…", "done": False}}
    assert started["x_ai_core"] == {"progress": {"stage": "generate"}}

    done = status_chunk(Status("Concluído em 2,0 s", done=True), **ENVELOPE)
    assert done["event"]["data"]["done"] is True
    assert "x_ai_core" not in done
    assert done["id"] == started["id"] and done["object"] == "chat.completion.chunk"
