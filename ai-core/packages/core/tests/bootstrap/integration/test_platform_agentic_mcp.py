"""T044 — conversa `agentic` + MCP ponta a ponta pela API, no perfil `test` e sem rede (US3 cen. 3, clarificação 2).

A suíte troca duas portas na montagem: o provider do controller (um roteiro que pede a tool do servidor e depois
responde) e os transportes de MCP (um servidor programado). O resto é a plataforma de verdade — autenticação da 003,
grant, motor da 005, gateway da 004, registry da 007, API da 008 e trace da 009.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from bootstrap_testkit import AGENTIC_ASSISTANTS_YAML, DEMO_ENDPOINT, MCP_YAML, OIDC, MemoryConfig, body, write_config
from fastapi.testclient import TestClient
from graph_testkit import ANSWER, ScriptedController, tool_action

from ai_core.bootstrap.wiring import Platform, platform
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from ai_core.mcp.ports import RemoteTool

pytestmark = pytest.mark.us3

ECO = RemoteTool(
    name="eco",
    description="Devolve o texto recebido.",
    input_schema={"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]},
)

CONTROLLER_PROGRAMADO = AGENTIC_ASSISTANTS_YAML.replace(
    "      controller: ollama/qwen3:1.7b\n      allow: [\"ollama/*\"]\n  perdido:",
    "      controller: ctrl/controlador\n      allow: [\"ollama/*\", \"ctrl/*\"]\n  perdido:",
)
"""`pesquisador` com o controller no provider `ctrl`, que a suíte troca na montagem."""


SEM_MCP = AGENTIC_ASSISTANTS_YAML.replace("    mcp: [demo]\n", "")
"""`pesquisador` sem servidor MCP: o catálogo é só a tool do pack (`generic.calculate`)."""


def _plataforma(tmp_path: Path, *, assistants: str, mcp: str | None = MCP_YAML, **overrides: Any) -> Platform:
    settings = write_config(tmp_path, assistants=assistants, mcp=mcp)
    plataforma = platform(config=MemoryConfig(settings), overrides=overrides or None)
    assert plataforma.ok, plataforma.report.render()
    return plataforma


def test_o_controller_pede_a_tool_do_servidor_e_a_resposta_chega_pela_api(tmp_path: Path) -> None:
    transporte = ScriptedMcpTransport({DEMO_ENDPOINT: ScriptedServer(tools=(ECO,))})
    controller = ScriptedController([tool_action("demo.eco", texto="olá"), ANSWER])
    plataforma = _plataforma(
        tmp_path,
        assistants=CONTROLLER_PROGRAMADO,
        providers={"ollama": ScriptedProvider(name="ollama", deltas=("Pronto.",)), "ctrl": controller},
        mcp_transports={"http": transporte, "sse": transporte, "stdio": transporte},
    )

    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="pesquisador"))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["choices"][0]["message"]["content"] == "Pronto."
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert [operation for operation, _ in transporte.calls if operation.startswith("call_tool")] == ["call_tool:eco"]
    assert len(controller.calls) == 2

    assert plataforma.trace is not None
    tipos = [record.type for record in plataforma.trace.trace(payload["x_ai_core"]["request_id"]).records]
    assert "controller_decision" in tipos and "tool_call" in tipos


def test_sem_trocas_o_controller_simulado_responde_direto(tmp_path: Path) -> None:
    """O perfil `test` sozinho já atende um Assistant `agentic`: o controller simulado responde direto."""
    plataforma = _plataforma(tmp_path, assistants=SEM_MCP, mcp=None)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="pesquisador"))
    assert response.status_code == 200, response.text
    assert response.json()["choices"][0]["message"]["content"] == "Brasília"
    assert response.json()["choices"][0]["finish_reason"] == "stop"


def test_servidor_mcp_fora_do_ar_e_falha_explicita_e_a_resposta_ainda_chega(tmp_path: Path) -> None:
    """Sem servidor programado, `demo` não responde: a execução segue sem a tool e registra `McpUnavailable` como
    erro — degradação explícita (princípio VII; 005 R23). Sem streaming, a 008 responde 502 com a resposta no corpo."""
    plataforma = _plataforma(tmp_path, assistants=AGENTIC_ASSISTANTS_YAML)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="pesquisador"))
    assert response.status_code == 502
    payload = response.json()
    assert payload["choices"][0]["message"]["content"] == "Brasília"
    assert [e["kind"] for e in payload["x_ai_core"]["errors"]] == ["McpUnavailable"]
