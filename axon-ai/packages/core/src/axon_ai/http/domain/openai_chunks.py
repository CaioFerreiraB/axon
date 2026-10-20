"""Construção das respostas no formato OpenAI: pura, testável sem servidor (research R4).

É aqui que moram os detalhes que quebram cliente — papel só no primeiro chunk, `finish_reason` só no último, progresso
como raciocínio só antes do texto — e por isso eles ficam fora do adapter (contracts/sse-format.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

from axon_ai.graph.api import ExecutionIssue, FinalEvent, ProgressEvent, TokenEvent
from axon_ai.http.domain.progress_text import QUEUE_STAGE, progress_line, queue_line
from axon_ai.http.domain.timeline import Status

CHUNK_OBJECT: Final = "chat.completion.chunk"
COMPLETION_OBJECT: Final = "chat.completion"
ASSISTANT_ROLE: Final = "assistant"
FINISH_STOP: Final = "stop"
FINISH_ERROR: Final = "error"
EXTRA: Final = "x_axon"
OPEN_WEBUI_EVENT: Final = "event"
"""Chave que o Open WebUI v0.12 repassa ao emissor de eventos dele (research R42)."""


def _envelope(*, request_id: str, model: str, created: datetime, object_type: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{request_id}",
        "object": object_type,
        "created": int(created.timestamp()),
        "model": model,
    }


def _chunk(*, request_id: str, model: str, created: datetime, delta: dict[str, Any], **extra: Any) -> dict[str, Any]:
    body = _envelope(request_id=request_id, model=model, created=created, object_type=CHUNK_OBJECT)
    choice: dict[str, Any] = {"index": 0, "delta": delta, "finish_reason": extra.get("finish_reason")}
    body["choices"] = [choice]
    if EXTRA in extra:
        body[EXTRA] = extra[EXTRA]
    return body


def opening_chunk(
    *, request_id: str, model: str, created: datetime, conversation_id: str | None = None
) -> dict[str, Any]:
    """Abre a mensagem. O papel vai só aqui: repetido, confunde alguns clientes. O id da conversa também — é o que
    permite ao cliente continuá-la mesmo que a execução ainda não tenha terminado (FR-014)."""
    extra: dict[str, Any] = {} if conversation_id is None else {EXTRA: {"conversation_id": conversation_id}}
    return _chunk(request_id=request_id, model=model, created=created, delta={"role": ASSISTANT_ROLE}, **extra)


def token_chunk(event: TokenEvent, *, request_id: str, model: str, created: datetime) -> dict[str, Any]:
    return _chunk(request_id=request_id, model=model, created=created, delta={"content": event.text})


def progress_chunk(
    event: ProgressEvent, *, request_id: str, model: str, created: datetime, reasoning: bool = True
) -> dict[str, Any]:
    """Progresso no campo extra (research R5) e, antes do texto da resposta, também como uma linha de raciocínio
    (`reasoning_content`), que o Open WebUI mostra à parte e o cliente padrão ignora (FR-005, R34). Depois do primeiro
    token, `reasoning=False`: uma linha ali abriria um segundo bloco de "pensamento" abaixo da resposta."""
    delta = {"reasoning_content": progress_line(event.stage, event.detail) + "\n"} if reasoning else {}
    return _chunk(
        request_id=request_id, model=model, created=created, delta=delta, **{EXTRA: {"progress": progress_of(event)}}
    )


def progress_of(event: ProgressEvent) -> dict[str, Any]:
    """O progresso no campo extra (research R5): a etapa e, quando há, o detalhe."""
    progress: dict[str, Any] = {"stage": event.stage}
    if event.detail is not None:
        progress["detail"] = event.detail
    return progress


def status_chunk(
    status: Status, *, request_id: str, model: str, created: datetime, progress: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Um item da timeline do Open WebUI (FR-005a, research R42): `delta` vazio e o status na chave `event`, que o
    v0.12 repassa ao emissor de eventos dele e grava na mensagem. O início de etapa e a fila levam também o
    `x_axon.progress` de sempre; o cliente padrão ignora as duas chaves."""
    extra: dict[str, Any] = {} if progress is None else {EXTRA: {"progress": progress}}
    body = _chunk(request_id=request_id, model=model, created=created, delta={}, **extra)
    body[OPEN_WEBUI_EVENT] = {"type": "status", "data": {"description": status.description, "done": status.done}}
    return body


def queue_chunk(*, position: int, request_id: str, model: str, created: datetime) -> dict[str, Any]:
    """O aviso de fila (FR-017): sai logo depois da abertura, antes de qualquer evento do motor."""
    return _chunk(
        request_id=request_id,
        model=model,
        created=created,
        delta={"reasoning_content": queue_line(position) + "\n"},
        **{EXTRA: {"progress": queue_progress(position)}},
    )


def queue_progress(position: int) -> dict[str, Any]:
    return {"stage": QUEUE_STAGE, "detail": str(position)}


def final_chunk(event: FinalEvent, *, request_id: str, model: str, created: datetime) -> dict[str, Any]:
    return _chunk(
        request_id=request_id,
        model=model,
        created=created,
        delta={},
        finish_reason=finish_reason(event),
        **{EXTRA: extra_field(event, request_id=request_id)},
    )


def completion(
    event: FinalEvent, *, request_id: str, model: str, created: datetime, conversation_id: str | None = None
) -> dict[str, Any]:
    """Resposta sem streaming: um objeto só, com a resposta inteira."""
    body = _envelope(request_id=request_id, model=model, created=created, object_type=COMPLETION_OBJECT)
    body["choices"] = [
        {
            "index": 0,
            "message": {"role": ASSISTANT_ROLE, "content": event.answer},
            "finish_reason": finish_reason(event),
        }
    ]
    body[EXTRA] = extra_field(event, request_id=request_id)
    if conversation_id is not None:
        body[EXTRA]["conversation_id"] = conversation_id
    return body


def finish_reason(event: FinalEvent) -> str:
    """`error` só quando algum registro tem gravidade `error` (FR-022, ADR-018).

    Registro `notice` — apontamento de validator, limite de iterações, ação inválida, corte de contexto — não é falha:
    a resposta sai com o registro no campo extra. A API decide pela gravidade e não conhece `kind` nenhum da 005.
    """
    return FINISH_ERROR if any(issue.severity == "error" for issue in event.errors) else FINISH_STOP


def extra_field(event: FinalEvent, *, request_id: str) -> dict[str, Any]:
    """Onde a plataforma diz o que o formato da OpenAI não tem onde dizer. Clientes padrão ignoram."""
    return {
        "request_id": request_id,
        "citations": [dict(citation) for citation in event.citations],
        "flags": sorted(event.flags),
        "errors": _issues(event.errors),
    }


def _issues(issues: Sequence[ExecutionIssue]) -> list[dict[str, str]]:
    return [{"stage": issue.stage, "kind": issue.kind, "message": issue.message} for issue in issues]
