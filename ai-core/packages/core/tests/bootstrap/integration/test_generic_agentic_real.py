"""010 US2 (T020) — o Assistant genérico com um modelo de verdade: o cenário 1 literal (research R19).

Pulado por default: roda só com `OLLAMA_BASE_URL` definida (o mesmo gatilho da integração da 006; ver o quickstart da
010, "Fase 3" §11). O MCP continua programado — sem rede além do Ollama —, e a tool devolve um código que o modelo não
tem como adivinhar: se ele aparece na resposta, o controller chamou a tool e a geração usou o resultado.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from bootstrap_testkit import DEMO_ENDPOINT, OIDC, PUBLICO, USER_ASSISTANTS_E_ADMIN, MemoryConfig, write_config
from fastapi.testclient import TestClient

from ai_core.bootstrap.wiring import platform
from ai_core.llm.adapters.ollama import OllamaProvider
from ai_core.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from ai_core.mcp.ports import RemotePart, RemoteResult, RemoteTool

BASE_URL = os.environ.get("OLLAMA_BASE_URL")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")

pytestmark = [
    pytest.mark.us2,
    pytest.mark.skipif(BASE_URL is None, reason="defina OLLAMA_BASE_URL para rodar contra um Ollama real"),
]

CODIGO = "QX-4471-ZP"

CONSULTAR = RemoteTool(
    name="consultar_registro",
    description="Devolve o código de confirmação de um registro pelo número.",
    input_schema={"type": "object", "properties": {"numero": {"type": "string"}}, "required": ["numero"]},
)

SERVIDOR = ScriptedServer(
    tools=(CONSULTAR,),
    results={
        "consultar_registro": RemoteResult(
            parts=(RemotePart(kind="text", text=f"Código de confirmação do registro 17: {CODIGO}"),)
        )
    },
)

MCP = f"""
servers:
  demo:
    transport: http
    endpoint: {DEMO_ENDPOINT}
    policy:
      allowed_tools: [consultar_registro]
"""

ASSISTANTS = f"""
assistants:
  geral:{PUBLICO}
    flow: agentic
    packs: [generic]
    mcp: [demo]
    models:
      generation: ollama/{MODEL}
      controller: ollama/{MODEL}
      allow: ["ollama/*"]
{USER_ASSISTANTS_E_ADMIN}"""


def test_a_resposta_usa_o_resultado_da_tool_do_mcp(tmp_path: Path) -> None:
    transporte = ScriptedMcpTransport({DEMO_ENDPOINT: SERVIDOR})
    plataforma = platform(
        config=MemoryConfig(write_config(tmp_path, assistants=ASSISTANTS, mcp=MCP)),
        overrides={
            "providers": {"ollama": OllamaProvider(base_url=BASE_URL or "")},
            "mcp_transports": {"http": transporte, "sse": transporte, "stdio": transporte},
        },
    )
    assert plataforma.ok, plataforma.report.render()

    pergunta = "Qual é o código de confirmação do registro 17? Consulte a ferramenta."
    with TestClient(plataforma.app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers=OIDC,
            json={"model": "geral", "messages": [{"role": "user", "content": pergunta}]},
        )

    assert response.status_code == 200, response.text
    assert any(operation == "call_tool:consultar_registro" for operation, _ in transporte.calls), transporte.calls
    assert CODIGO in response.json()["choices"][0]["message"]["content"]
