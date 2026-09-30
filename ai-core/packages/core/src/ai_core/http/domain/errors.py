"""Erros da API no envelope da OpenAI (contracts/errors.md, research R14): a tabela exceção → status, pura.

Os erros de acesso e de pedido vêm da 003 com o campo que os causou; os de formato de requisição nascem aqui. O
adapter só escreve o que esta tabela decide — nenhum status é escolhido numa rota.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from ai_core.assistants.api import (
    AssistantNotFound,
    AssistantUnavailable,
    Conflict,
    NoApplicablePolicy,
    NotFound,
    PolicyViolation,
    RateLimited,
    RequestRejected,
)
from ai_core.graph.api import ExecutionRequestInvalid

EXTRA: Final = "x_ai_core"
ASSISTANT_NOT_FOUND: Final = "assistant não encontrado"
NOT_FOUND: Final = "recurso não encontrado"
"""Mensagens fixas do 404: o corpo é idêntico para inexistente e não autorizado — nem o nome pedido volta (SC-001)."""
MODEL_NOT_ALLOWED_PREFIX: Final = "modelo não permitido"


class InvalidRequest(ValueError):
    """Corpo recusado. `field` nomeia o campo; `code` distingue ampliação e data de referência do erro comum."""

    def __init__(self, message: str, *, field: str | None = None, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.field = field
        self.code = code


class ConversationMismatch(InvalidRequest):
    """`conversation_id` de uma conversa de outro Assistant: recusado antes de executar."""

    def __init__(self, message: str) -> None:
        super().__init__(message, field="conversation_id", code="conversation_assistant_mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorResponse:
    status: int
    type: str
    code: str
    message: str
    param: str | None = None
    retry_after: int | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error": {"message": self.message, "type": self.type, "param": self.param, "code": self.code}
        }
        if self.extra:
            body[EXTRA] = dict(self.extra)
        return body

    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(self.retry_after)} if self.retry_after is not None else {}


def unauthenticated() -> ErrorResponse:
    return ErrorResponse(
        status=401, type="authentication_error", code="invalid_credential", message="credencial ausente ou recusada"
    )


def error_for(error: BaseException) -> ErrorResponse | None:
    """A resposta de uma exceção conhecida, ou `None` — erro inesperado continua sendo 500 do framework."""
    message = str(error)
    match error:
        case AssistantNotFound():
            return ErrorResponse(status=404, type="not_found_error", code="not_found", message=ASSISTANT_NOT_FOUND)
        case NotFound():
            return ErrorResponse(status=404, type="not_found_error", code="not_found", message=NOT_FOUND)
        case NoApplicablePolicy():
            return _invalid(message, "no_applicable_policy", error.field)
        case PolicyViolation():
            return _invalid(message, "policy_violation", error.field)
        case RequestRejected():
            code = "model_not_allowed" if message.startswith(MODEL_NOT_ALLOWED_PREFIX) else "invalid_request"
            return _invalid(message, code, error.field)
        case InvalidRequest():
            return _invalid(message, error.code, error.field)
        case ExecutionRequestInvalid():
            return _invalid(message, "invalid_request", None)
        case Conflict():
            return ErrorResponse(status=409, type="conflict_error", code="conflict", message=message, param="name")
        case AssistantUnavailable():
            return ErrorResponse(
                status=424,
                type="dependency_error",
                code="assistant_unavailable",
                message=message,
                extra={"reasons": list(error.reasons)},
            )
        case RateLimited():
            return ErrorResponse(
                status=429,
                type="rate_limit_error",
                code="rate_limit_exceeded",
                message=message,
                retry_after=max(1, math.ceil(error.retry_after)),
            )
    return None


def _invalid(message: str, code: str, param: str | None) -> ErrorResponse:
    return ErrorResponse(status=400, type="invalid_request_error", code=code, message=message, param=param)
