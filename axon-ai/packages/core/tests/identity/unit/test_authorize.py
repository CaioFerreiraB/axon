"""T021 — validação do pedido de autorização (FR-004, FR-005; contracts/oidc.md)."""

from __future__ import annotations

import pytest
from identity_testkit import CONSOLE, OPEN_WEBUI, authorize_params, pkce_pair

from axon_ai.identity.domain.authorize import AuthorizationRequest, NoRedirect, RedirectError, read_authorization

CLIENTS = {OPEN_WEBUI.id: OPEN_WEBUI, CONSOLE.id: CONSOLE}
_, CHALLENGE = pkce_pair()


def test_pedido_valido_de_cliente_confidencial() -> None:
    request = read_authorization(authorize_params(OPEN_WEBUI, scope="openid profile foo email openid"), CLIENTS)
    assert isinstance(request, AuthorizationRequest)
    assert request.client == OPEN_WEBUI and request.redirect_uri == OPEN_WEBUI.redirect_uris[0]
    assert request.scope == "openid profile email"
    assert (request.state, request.nonce, request.code_challenge, request.prompt) == ("estado-1", "nonce-1", None, None)


def test_pedido_valido_de_cliente_publico_com_pkce() -> None:
    request = read_authorization(authorize_params(CONSOLE, challenge=CHALLENGE), CLIENTS)
    assert isinstance(request, AuthorizationRequest) and request.code_challenge == CHALLENGE


@pytest.mark.parametrize(
    "params",
    [
        authorize_params(OPEN_WEBUI, client_id="desconhecido"),
        authorize_params(OPEN_WEBUI, redirect_uri="http://localhost:3000/oauth/oidc/callback/"),
        authorize_params(OPEN_WEBUI, redirect_uri="https://atacante.exemplo/cb"),
        authorize_params(OPEN_WEBUI, redirect_uri=CONSOLE.redirect_uris[0]),
        {k: v for k, v in authorize_params(OPEN_WEBUI).items() if k != "redirect_uri"},
    ],
)
def test_cliente_ou_redirect_invalidos_nunca_redirecionam(params: dict[str, str]) -> None:
    assert isinstance(read_authorization(params, CLIENTS), NoRedirect)


@pytest.mark.parametrize(
    ("params", "error"),
    [
        (authorize_params(OPEN_WEBUI, response_type="token"), "unsupported_response_type"),
        (authorize_params(OPEN_WEBUI, response_type="code id_token"), "unsupported_response_type"),
        (authorize_params(OPEN_WEBUI, scope="profile email"), "invalid_scope"),
        (authorize_params(OPEN_WEBUI, nonce=""), "invalid_request"),
        (authorize_params(OPEN_WEBUI, nonce="n" * 513), "invalid_request"),
        (authorize_params(OPEN_WEBUI, state="s" * 1025), "invalid_request"),
        (authorize_params(CONSOLE), "invalid_request"),
        (authorize_params(CONSOLE, code_challenge=CHALLENGE, code_challenge_method="plain"), "invalid_request"),
        (authorize_params(CONSOLE, code_challenge="curto", code_challenge_method="S256"), "invalid_request"),
        (authorize_params(OPEN_WEBUI, code_challenge_method="S256"), "invalid_request"),
        (authorize_params(OPEN_WEBUI, prompt="none login"), "invalid_request"),
    ],
)
def test_erros_voltam_ao_cliente_com_o_state(params: dict[str, str], error: str) -> None:
    outcome = read_authorization(params, CLIENTS)
    assert isinstance(outcome, RedirectError)
    assert outcome.error == error and outcome.redirect_uri == params["redirect_uri"]
    assert outcome.state == params["state"][:1025] or error == "invalid_request"


@pytest.mark.parametrize(("prompt", "expected"), [("login", "login"), ("none", "none"), ("consent", None)])
def test_prompt(prompt: str, expected: str | None) -> None:
    request = read_authorization(authorize_params(OPEN_WEBUI, prompt=prompt), CLIENTS)
    assert isinstance(request, AuthorizationRequest) and request.prompt == expected


async def test_prompt_none_sem_sessao_e_login_required() -> None:
    from identity_testkit import harness, query

    from axon_ai.identity.domain.outcomes import Redirect

    parts = harness()
    await parts.service.start()
    outcome = await parts.service.authorize(authorize_params(OPEN_WEBUI, prompt="none"), None)
    assert isinstance(outcome, Redirect)
    assert query(outcome.location) == {
        "error": "login_required",
        "error_description": "sem sessão",
        "state": "estado-1",
    }
