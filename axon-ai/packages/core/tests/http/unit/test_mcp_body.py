"""T047 — corpo de servidor MCP ⇄ seam da 007 (contracts/mcp-routes.md; research R26), na forma do `mcp.yaml`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from axon_ai.http.domain.errors import InvalidRequest
from axon_ai.http.domain.mcp_body import draft_from_json, health_json, server_json, summary_json
from axon_ai.mcp.api import McpServer, McpSummary, SecurityPolicy, ServerHealth

pytestmark = pytest.mark.us4

AT = datetime(2026, 10, 2, 12, tzinfo=UTC)

CORPO: dict[str, Any] = {
    "alias": "financeiro",
    "transport": "http",
    "endpoint": "http://mcp-financeiro:8080/mcp",
    "description": "Saldos",
    "auth": {"type": "bearer", "credential": "financeiro_token"},
    "enabled": True,
    "user_access": False,
    "policy": {"allowed_tools": ["saldo", "pagar"], "write_tools": ["pagar"], "timeout_ms": 10000},
}


def test_corpo_completo_vira_rascunho() -> None:
    draft = draft_from_json(CORPO, scope="global")
    assert (draft.alias, draft.transport, draft.endpoint, draft.description) == (
        "financeiro",
        "http",
        "http://mcp-financeiro:8080/mcp",
        "Saldos",
    )
    assert (draft.auth_type, draft.credential_ref, draft.enabled, draft.user_access) == (
        "bearer",
        "financeiro_token",
        True,
        False,
    )
    assert draft.policy.allowed_tools == ("saldo", "pagar")
    assert draft.policy.write_tools == ("pagar",)
    assert draft.policy.timeout_ms == 10000


def test_minimo_usa_os_defaults_da_007() -> None:
    draft = draft_from_json(
        {
            "alias": "~agenda",
            "transport": "http",
            "endpoint": "https://a.example/mcp",
            "policy": {"allowed_tools": ["listar"]},
        },
        scope="user",
    )
    assert (draft.auth_type, draft.credential_ref, draft.enabled, draft.user_access) == ("none", None, True, False)


def test_no_escopo_de_usuario_o_alias_ganha_til() -> None:
    draft = draft_from_json({**CORPO, "alias": "agenda", "auth": None}, scope="user")
    assert draft.alias == "~agenda"


def test_alias_do_caminho_prevalece() -> None:
    assert draft_from_json(CORPO, scope="global", alias="outro").alias == "outro"
    assert draft_from_json({k: v for k, v in CORPO.items() if k != "alias"}, scope="user", alias="agenda").alias == (
        "~agenda"
    )


@pytest.mark.parametrize(
    ("corpo", "campo"),
    [
        ({**CORPO, "extra": 1}, "extra"),
        ({**CORPO, "auth": {"type": "bearer", "segredo": "x"}}, "auth.segredo"),
        ({**CORPO, "policy": {"allowed_tools": ["a"], "regex": "x"}}, "policy.regex"),
        ({**CORPO, "transport": ["http"]}, "transport"),
        ({**CORPO, "policy": "tudo"}, "policy"),
        ({**CORPO, "enabled": "sim"}, "enabled"),
        ({k: v for k, v in CORPO.items() if k != "alias"}, "alias"),
        ({k: v for k, v in CORPO.items() if k != "policy"}, "policy"),
    ],
)
def test_corpo_invalido_nomeia_o_campo(corpo: dict[str, Any], campo: str) -> None:
    with pytest.raises(InvalidRequest) as erro:
        draft_from_json(corpo, scope="global")
    assert erro.value.field == campo


def _servidor(**overrides: Any) -> McpServer:
    fields: dict[str, Any] = {
        "alias": "financeiro",
        "scope": "global",
        "owner": None,
        "transport": "http",
        "endpoint": "http://mcp-financeiro:8080/mcp",
        "auth_type": "bearer",
        "credential_ref": "financeiro_token",
        "policy": SecurityPolicy(allowed_tools=("saldo",)),
        "origin": "registry",
        "created_at": AT,
        "updated_at": AT,
    }
    return McpServer(**(fields | overrides))


def test_servidor_em_json_so_com_o_nome_da_referencia() -> None:
    corpo = server_json(_servidor())
    assert corpo["auth"] == {"type": "bearer", "credential": "financeiro_token"}
    assert corpo["policy"]["allowed_tools"] == ["saldo"]
    for chave in (
        "alias",
        "scope",
        "owner",
        "transport",
        "endpoint",
        "command",
        "description",
        "enabled",
        "user_access",
        "origin",
        "available",
        "reason",
        "created_at",
        "updated_at",
    ):
        assert chave in corpo
    assert corpo["created_at"] == AT.isoformat()


def test_entrada_do_arquivo_com_erro_sai_sem_politica() -> None:
    corpo = server_json(_servidor(transport=None, policy=None, origin="file", available=False, reason="sem política"))
    assert corpo["policy"] is None and corpo["available"] is False and corpo["reason"] == "sem política"


def test_resumo_sem_endpoint_nem_politica() -> None:
    assert summary_json(McpSummary(alias="~agenda", scope="user", description="minha")) == {
        "alias": "~agenda",
        "scope": "user",
        "description": "minha",
    }


def test_saude_em_json() -> None:
    saude = ServerHealth(alias="financeiro", ok=False, detail="fora", tools=("saldo",), missing=("pagar",))
    assert health_json(saude) == {
        "alias": "financeiro",
        "ok": False,
        "detail": "fora",
        "tools": ["saldo"],
        "missing": ["pagar"],
    }
