"""Erros da API no envelope da OpenAI (contracts/errors.md, research R14): a tabela exceção → status, pura.

Os erros de acesso e de pedido vêm da 003 com o campo que os causou; os de formato de requisição nascem aqui. O
adapter só escreve o que esta tabela decide — nenhum status é escolhido numa rota.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from axon_ai.assistants.api import (
    AssistantNotFound,
    AssistantUnavailable,
    Conflict,
    NoApplicablePolicy,
    NotFound,
    PolicyViolation,
    RateLimited,
    RequestRejected,
)
from axon_ai.graph.api import ExecutionRequestInvalid
from axon_ai.http.domain.admin_common import AdminInvalid
from axon_ai.identity import api as identity
from axon_ai.llm.api import ModelRoutingError
from axon_ai.mcp.api import McpConflict, UnknownServer
from axon_ai.observability import api as observability

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


class Overloaded(Exception):
    """Vagas e fila cheias, ou espera esgotada sem streaming (FR-016, FR-017): 503, antes de qualquer modelo."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"a plataforma está no limite de execuções simultâneas; tente de novo em {retry_after} s")
        self.retry_after = retry_after


QUEUE_TIMEOUT_KIND: Final = "QueueTimeout"
QUEUE_TIMEOUT_STAGE: Final = "admission"
"""O registro do chunk final quando a espera na fila esgota com o stream já aberto (FR-017, R35)."""


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
    detail: Mapping[str, Any] = field(default_factory=dict)
    """Campos a mais dentro de `error` — `current_version` no conflito de versão da administração (R46)."""

    def body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error": {
                "message": self.message,
                "type": self.type,
                "param": self.param,
                "code": self.code,
                **self.detail,
            }
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


def storage_unavailable() -> ErrorResponse:
    """O armazenamento de credenciais não respondeu (FR-021). Mensagem fixa: nada da infraestrutura vai ao cliente."""
    return ErrorResponse(
        status=503,
        type="server_error",
        code="storage_unavailable",
        message="armazenamento de credenciais indisponível; tente de novo",
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
        case McpConflict():
            return ErrorResponse(status=409, type="conflict_error", code="conflict", message=message, param="alias")
        case Conflict():
            return ErrorResponse(status=409, type="conflict_error", code="conflict", message=message, param="name")
        case UnknownServer():
            return ErrorResponse(status=404, type="not_found_error", code="not_found", message=NOT_FOUND)
        case AssistantUnavailable():
            return ErrorResponse(
                status=424,
                type="dependency_error",
                code="assistant_unavailable",
                message=message,
                extra={"reasons": list(error.reasons)},
            )
        case Overloaded():
            # Sem `x-should-retry`: nada rodou, e repetir depois do `Retry-After` é seguro (contracts/errors.md).
            return ErrorResponse(
                status=503, type="server_error", code="overloaded", message=message, retry_after=error.retry_after
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


# --- superfície de administração (Fase 9, research R46) ------------------------------------------------------------


def _conflict(code: str, message: str, *, param: str | None = None, **detail: Any) -> ErrorResponse:
    return ErrorResponse(status=409, type="conflict_error", code=code, message=message, param=param, detail=detail)


def _admin_invalid(message: str, param: str | None) -> ErrorResponse:
    return ErrorResponse(status=422, type="invalid_request_error", code="invalid_field", message=message, param=param)


def admin_error_for(error: BaseException) -> ErrorResponse | None:
    """A tabela da administração (contracts/admin-api.md, "Erros"): validação é 422 `invalid_field` com `param`; os
    conflitos têm um código por causa; inexistente e não autorizado são o mesmo 404."""
    message = str(error)
    match error:
        case AdminInvalid():
            return _admin_invalid(message, error.field)
        case NotFound() | identity.AccountNotFound() | identity.GroupNotFound() | UnknownServer():
            return ErrorResponse(status=404, type="not_found_error", code="not_found", message=NOT_FOUND)
        case RequestRejected():
            return _admin_invalid(message, error.field)
        case identity.InvalidField() | observability.InvalidField() | observability.InvalidPrice():
            return _admin_invalid(message, error.field)
        case observability.InvalidQuery():
            return _admin_invalid(message, {"start": "from", "end": "to"}.get(error.field, error.field))
        case identity.InstallationDefined() | observability.InstallationDefined():
            return _conflict("installation_defined", message, param=error.field)
        case observability.MasterKeyMissing():
            return _conflict("master_key_missing", message, param="secret_key")
        case identity.ProtectedGroup():
            return _conflict("protected_group", message)
        case identity.GoogleNotConfigured():
            return _conflict("google_not_configured", message, param="google_enabled")
        case identity.Conflict():
            if error.field == "version":
                return _conflict("version_conflict", message, param="version", current_version=error.current_version)
            return _conflict("conflict", message, param=error.field)
        case Conflict() | observability.Conflict():
            return _conflict(
                "version_conflict", message, param="version", current_version=getattr(error, "current_version", None)
            )
        case McpConflict():
            return _conflict("conflict", message, param="alias")
        case ModelRoutingError():
            return _admin_invalid(message, "model")
    return None
