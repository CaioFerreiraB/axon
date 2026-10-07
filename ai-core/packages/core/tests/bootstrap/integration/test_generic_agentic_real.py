"""010 US2 (T020) — o Assistant genérico com um modelo de verdade: o cenário 1 literal (research R19).

Pulado por default. Roda contra o Ollama com `OLLAMA_BASE_URL` e contra o OpenRouter com
`AI_CORE_OPENROUTER_API_KEY` (chamada paga; modelo em `OPENROUTER_MODEL`) — os mesmos gatilhos das integrações da 006;
ver o quickstart da 010, "Fase 3" §11. Os dois papéis vão ao mesmo modelo, e o controller recebe o esquema de ação real
da 005. O MCP continua programado — sem rede além do provider —, e a tool devolve um código que o modelo não tem como
adivinhar: se ele aparece na resposta, o controller chamou a tool e a geração usou o resultado.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from bootstrap_testkit import DEMO_ENDPOINT, OIDC, PUBLICO, USER_ASSISTANTS_E_ADMIN, MemoryConfig, write_config
from fastapi.testclient import TestClient

from ai_core.bootstrap.wiring import platform
from ai_core.llm.adapters.ollama import OllamaProvider
from ai_core.llm.adapters.openrouter import OpenRouterProvider
from ai_core.llm.adapters.secrets import EnvSecretResolver
from ai_core.llm.ports import ModelProvider
from ai_core.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from ai_core.mcp.ports import RemotePart, RemoteResult, RemoteTool

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "~z-ai/glm-flash-latest")
"""Precisa de `structured_outputs` no OpenRouter: o controller exige esquema (006 R18). O mesmo default da 006."""

pytestmark = pytest.mark.us2


def _ollama() -> ModelProvider:
    return OllamaProvider(base_url=OLLAMA_BASE_URL or "")


def _openrouter() -> ModelProvider:
    return OpenRouterProvider(secrets=EnvSecretResolver())


BACKENDS = pytest.mark.parametrize(
    ("make", "model"),
    [
        pytest.param(
            _ollama,
            f"ollama/{OLLAMA_MODEL}",
            id="ollama",
            marks=pytest.mark.skipif(
                OLLAMA_BASE_URL is None, reason="defina OLLAMA_BASE_URL para rodar contra um Ollama real"
            ),
        ),
        pytest.param(
            _openrouter,
            f"openrouter/{OPENROUTER_MODEL}",
            id="openrouter",
            marks=pytest.mark.skipif(
                not os.environ.get(OpenRouterProvider.CREDENTIAL),
                reason=f"defina {OpenRouterProvider.CREDENTIAL} para rodar contra o OpenRouter (pago)",
            ),
        ),
    ],
)

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



def _assistants(model: str) -> str:
    provider = model.partition("/")[0]
    return f"""
assistants:
  geral:{PUBLICO}
    flow: agentic
    packs: [generic]
    mcp: [demo]
    models:
      generation: {model}
      controller: {model}
      allow: ["{provider}/*"]
{USER_ASSISTANTS_E_ADMIN}"""


@BACKENDS
def test_a_resposta_usa_o_resultado_da_tool_do_mcp(tmp_path: Path, make: Any, model: str) -> None:
    transporte = ScriptedMcpTransport({DEMO_ENDPOINT: SERVIDOR})
    provider = make()
    plataforma = platform(
        config=MemoryConfig(write_config(tmp_path, assistants=_assistants(model), mcp=MCP)),
        overrides={
            "providers": {provider.name: provider},
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
