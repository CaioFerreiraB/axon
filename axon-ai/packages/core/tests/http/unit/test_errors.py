"""T022 — envelope de erro da OpenAI e a tabela de status (contracts/errors.md, research R14)."""

from __future__ import annotations

import pytest

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
from axon_ai.http.domain.errors import (
    ConversationMismatch,
    InvalidRequest,
    error_for,
    storage_unavailable,
    unauthenticated,
)


def test_envelope_tem_os_quatro_campos_da_openai() -> None:
    body = error_for(RequestRejected("modelo não permitido: y", field="model")).body()
    assert set(body["error"]) == {"message", "type", "param", "code"}
    assert body["error"]["message"] == "modelo não permitido: y"


@pytest.mark.parametrize(
    ("error", "status", "type_", "code", "param"),
    [
        (InvalidRequest("x", field="messages"), 400, "invalid_request_error", "invalid_request", "messages"),
        (
            InvalidRequest("x", field="tools", code="widening_field"),
            400,
            "invalid_request_error",
            "widening_field",
            "tools",
        ),
        (
            RequestRejected("modelo não permitido: y", field="model"),
            400,
            "invalid_request_error",
            "model_not_allowed",
            "model",
        ),
        (RequestRejected("x", field="subject"), 400, "invalid_request_error", "invalid_request", "subject"),
        (PolicyViolation("x", field="limits.rpm"), 400, "invalid_request_error", "policy_violation", "limits.rpm"),
        (NoApplicablePolicy("x", field="policy"), 400, "invalid_request_error", "no_applicable_policy", "policy"),
        (ConversationMismatch("x"), 400, "invalid_request_error", "conversation_assistant_mismatch", "conversation_id"),
        (ExecutionRequestInvalid("x"), 400, "invalid_request_error", "invalid_request", None),
        (Conflict("x"), 409, "conflict_error", "conflict", "name"),
        (AssistantUnavailable("x", reasons=["packs: y"]), 424, "dependency_error", "assistant_unavailable", None),
        (RateLimited("x", retry_after=1.2), 429, "rate_limit_error", "rate_limit_exceeded", None),
    ],
)
def test_cada_causa_tem_o_seu_status(error: Exception, status: int, type_: str, code: str, param: str | None) -> None:
    response = error_for(error)
    assert response.status == status
    assert response.body()["error"] == {"message": str(error), "type": type_, "param": param, "code": code}


def test_404_tem_corpo_identico_para_inexistente_e_nao_autorizado() -> None:
    a = error_for(AssistantNotFound("assistant 'privado' não existe ou não é visível"))
    b = error_for(AssistantNotFound("assistant 'nada' não existe ou não é visível"))
    assert a is not None and b is not None and a.status == b.status == 404
    assert (
        a.body()
        == b.body()
        == {
            "error": {
                "message": "assistant não encontrado",
                "type": "not_found_error",
                "param": None,
                "code": "not_found",
            }
        }
    )
    outro = error_for(NotFound("chave 'x' não existe"))
    assert outro is not None and outro.body()["error"]["message"] == "recurso não encontrado"


def test_indisponivel_leva_os_motivos() -> None:
    body = error_for(AssistantUnavailable("x", reasons=["packs: pack 'y' em erro", "flow: z"])).body()
    assert body["x_axon"] == {"reasons": ["packs: pack 'y' em erro", "flow: z"]}


@pytest.mark.parametrize(("seconds", "header"), [(0.1, "1"), (1.0, "1"), (1.01, "2"), (45.0, "45")])
def test_retry_after_arredonda_para_cima(seconds: float, header: str) -> None:
    assert error_for(RateLimited("x", retry_after=seconds)).headers() == {"Retry-After": header}


def test_credencial_recusada_e_401() -> None:
    response = unauthenticated()
    assert response.status == 401
    assert response.body()["error"]["type"] == "authentication_error"


def test_armazenamento_de_credenciais_fora_e_503() -> None:
    """FR-021: nunca 401 — culparia a credencial — nem o 500 genérico."""
    response = storage_unavailable()
    assert response.status == 503
    assert response.body()["error"]["type"] == "server_error"
    assert response.body()["error"]["code"] == "storage_unavailable"
    assert "armazenamento" in response.message


def test_excecao_desconhecida_nao_tem_traducao() -> None:
    assert error_for(RuntimeError("x")) is None
