"""Construção das respostas no formato OpenAI: pura, testável sem servidor (research R4).

É aqui que moram os detalhes que quebram cliente — papel só no primeiro chunk, `finish_reason` só no último, progresso
com `delta` vazio — e por isso eles ficam fora do adapter (contracts/sse-format.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

from ai_core.graph.api import ExecutionIssue, FinalEvent, ProgressEvent, TokenEvent

CHUNK_OBJECT: Final = "chat.completion.chunk"
COMPLETION_OBJECT: Final = "chat.completion"
ASSISTANT_ROLE: Final = "assistant"
FINISH_STOP: Final = "stop"
FINISH_ERROR: Final = "error"
EXTRA: Final = "x_ai_core"
VALIDATOR_ISSUE: Final = "ValidatorIssue"


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


def progress_chunk(event: ProgressEvent, *, request_id: str, model: str, created: datetime) -> dict[str, Any]:
    """Progresso vai com `delta` vazio e campo extra: cliente padrão ignora e não vê texto espúrio (research R5)."""
    progress: dict[str, Any] = {"stage": event.stage}
    if event.detail is not None:
        progress["detail"] = event.detail
    return _chunk(
        request_id=request_id,
        model=model,
        created=created,
        delta={},
        **{EXTRA: {"progress": progress}},
    )


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
    """`error` só quando houve falha de execução.

    Apontamento de validator é achado sobre a resposta, não falha — a mesma regra que o motor aplica ao deixar a
    resposta sair com a marcação (005 `domain/outcome.py`).
    """
    return FINISH_STOP if all(issue.kind == VALIDATOR_ISSUE for issue in event.errors) else FINISH_ERROR


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
