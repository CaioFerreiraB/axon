"""T008 — construção dos chunks no formato OpenAI (contracts/sse-format.md), pura."""

from __future__ import annotations

from http_testkit import CREATED, MODEL_ID

from ai_core.graph.api import ExecutionIssue, FinalEvent, ProgressEvent, TokenEvent
from ai_core.http.domain.openai_chunks import (
    completion,
    final_chunk,
    opening_chunk,
    progress_chunk,
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


def test_progresso_vai_com_delta_vazio_e_campo_extra() -> None:
    chunk = progress_chunk(ProgressEvent(stage="generate"), **ENVELOPE)
    assert chunk["choices"][0]["delta"] == {}
    assert chunk["x_ai_core"]["progress"] == {"stage": "generate"}


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
    """Reprovar é achado sobre a resposta, não falha de execução — a mesma regra do motor."""
    final = FinalEvent(
        answer="Brasília",
        errors=(ExecutionIssue(stage="validate_answer", kind="ValidatorIssue", message="sem fonte"),),
    )
    assert final_chunk(final, **ENVELOPE)["choices"][0]["finish_reason"] == "stop"


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
