"""T009 e T032 — validação do registro e da entrada do arquivo (research R11; FR-012 a FR-015)."""

from __future__ import annotations

from typing import Any

import pytest
from mcp_testkit import global_draft, policy, user_draft

from ai_core.mcp.api import McpRejected, SecurityPolicy
from ai_core.mcp.domain.servers import validate_draft


def rejected(draft: Any, *, scope: str = "global", origin: str = "registry") -> str:
    with pytest.raises(McpRejected) as caught:
        validate_draft(draft, scope=scope, origin=origin)  # type: ignore[arg-type]
    return caught.value.field


# --- globais (T009, US1) ----------------------------------------------------------------------------------------------


@pytest.mark.us1
def test_global_valido_passa() -> None:
    draft = global_draft()
    assert validate_draft(draft, scope="global", origin="registry") == draft


@pytest.mark.us1
@pytest.mark.parametrize("alias", ["", "Financeiro", "fin.anceiro", "~financeiro", "-fin", "a" * 33, "fin anceiro"])
def test_alias_global_fora_da_gramatica(alias: str) -> None:
    assert rejected(global_draft(alias=alias)) == "alias"


@pytest.mark.us1
@pytest.mark.parametrize(
    "endpoint",
    [
        None,
        "",
        "mcp.financeiro.example/mcp",
        "ftp://mcp.financeiro.example/mcp",
        "https:///mcp",
        "https://user:senha@mcp.financeiro.example/mcp",
        "https://user@mcp.financeiro.example/mcp",
        "https://mcp.financeiro.example/mcp#frag",
    ],
)
def test_endpoint_invalido(endpoint: str | None) -> None:
    assert rejected(global_draft(endpoint=endpoint)) == "endpoint"


@pytest.mark.us1
def test_global_aceita_http_e_https() -> None:
    validate_draft(global_draft(endpoint="http://mcp-financeiro:8080/mcp"), scope="global", origin="registry")
    validate_draft(global_draft(transport="sse", endpoint="https://x.example/sse"), scope="global", origin="registry")


@pytest.mark.us1
def test_stdio_pela_api_e_recusado_nomeando_o_transporte() -> None:
    """FR-013: nem com chave de administração — seria execução remota de comando (ADR-003)."""
    assert rejected(global_draft(transport="stdio", endpoint=None)) == "transport"


@pytest.mark.us1
def test_transporte_desconhecido() -> None:
    assert rejected(global_draft(transport="websocket")) == "transport"


@pytest.mark.us1
def test_bearer_exige_referencia_e_referencia_exige_bearer() -> None:
    assert rejected(global_draft(auth_type="bearer")) == "credential_ref"
    assert rejected(global_draft(auth_type="none", credential_ref="token")) == "credential_ref"
    assert rejected(global_draft(auth_type="basic")) == "auth_type"
    ok = global_draft(auth_type="bearer", credential_ref="financeiro_token")
    assert validate_draft(ok, scope="global", origin="registry") == ok


@pytest.mark.us1
@pytest.mark.parametrize("ref", ["Token", "a-b", "_x", "a" * 65, "database url"])
def test_referencia_fora_da_gramatica(ref: str) -> None:
    assert rejected(global_draft(auth_type="bearer", credential_ref=ref)) == "credential_ref"


@pytest.mark.us1
def test_descricao_ate_500() -> None:
    validate_draft(global_draft(description="d" * 500), scope="global", origin="registry")
    assert rejected(global_draft(description="d" * 501)) == "description"


@pytest.mark.us1
@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"allowed_tools": ()}, "policy.allowed_tools"),
        ({"allowed_tools": ("a", "a")}, "policy.allowed_tools"),
        ({"allowed_tools": ("a", " ")}, "policy.allowed_tools"),
        ({"allowed_tools": ("a",), "write_tools": ("b",)}, "policy.write_tools"),
        ({"timeout_ms": 999}, "policy.timeout_ms"),
        ({"timeout_ms": 120_001}, "policy.timeout_ms"),
        ({"timeout_ms": True}, "policy.timeout_ms"),
        ({"max_response_bytes": 1023}, "policy.max_response_bytes"),
        ({"max_response_bytes": 1_048_577}, "policy.max_response_bytes"),
    ],
)
def test_politica_fora_das_regras(overrides: dict[str, Any], field: str) -> None:
    base: dict[str, Any] = {"allowed_tools": ("saldo",)}
    with pytest.raises(McpRejected) as caught:
        SecurityPolicy(**(base | overrides))
    assert caught.value.field == field


@pytest.mark.us1
def test_politica_padrao() -> None:
    p = SecurityPolicy(allowed_tools=("saldo",))
    assert (p.timeout_ms, p.max_response_bytes, p.write_tools) == (30_000, 65_536, ())


# --- de usuário (T032, US4) -------------------------------------------------------------------------------------------


@pytest.mark.us4
def test_usuario_valido_passa() -> None:
    draft = user_draft()
    assert validate_draft(draft, scope="user", origin="registry") == draft


@pytest.mark.us4
@pytest.mark.parametrize("alias", ["drive", "~", "~Drive", "~dr.ive", "~~drive"])
def test_alias_de_usuario_exige_til(alias: str) -> None:
    assert rejected(user_draft(alias=alias), scope="user") == "alias"


@pytest.mark.us4
def test_usuario_nao_usa_stdio() -> None:
    """US4 cen. 2."""
    assert rejected(user_draft(transport="stdio", endpoint=None), scope="user") == "transport"


@pytest.mark.us4
def test_usuario_so_https() -> None:
    assert rejected(user_draft(endpoint="http://drive.example/mcp"), scope="user") == "endpoint"


@pytest.mark.us4
def test_usuario_sem_autenticacao_nem_credencial() -> None:
    """US4 cen. 3: referenciar segredos do servidor permitiria enviá-los ao endpoint do próprio usuário."""
    assert rejected(user_draft(auth_type="bearer", credential_ref="x"), scope="user") == "auth_type"
    assert rejected(user_draft(credential_ref="financeiro_token"), scope="user") == "credential_ref"
    assert rejected(user_draft(endpoint="https://a:b@drive.example/mcp"), scope="user") == "endpoint"


@pytest.mark.us4
def test_usuario_nao_libera_a_usuarios() -> None:
    assert rejected(user_draft(user_access=True), scope="user") == "user_access"


@pytest.mark.us4
def test_global_com_til_e_recusado() -> None:
    """US4 cen. 5."""
    assert rejected(global_draft(alias="~financeiro")) == "alias"


@pytest.mark.us4
def test_politica_do_testkit_e_valida() -> None:
    assert policy().write_tools == ("pagar",)
