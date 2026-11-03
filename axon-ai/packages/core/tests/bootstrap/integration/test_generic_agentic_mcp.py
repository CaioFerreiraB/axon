"""010 US2 (T019) — o Assistant genérico com MCP no flow `agentic`, ponta a ponta pela API, no perfil `test` e sem rede.

`packs: [generic]` com o MCP `demo` do `mcp.yaml`: o controller (trocado na montagem) pede a tool do servidor e depois
responde; a geração recebe o prompt do pack e o resultado cercado. O prompt vem pelo seam `PackHooks` da 002 — o teste
não importa `axon_generic`, e nenhuma linha do core conhece o pack (010 SC-002, research R18).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from bootstrap_testkit import AGENTIC_ASSISTANTS_YAML, DEMO_ENDPOINT, MCP_YAML, OIDC, MemoryConfig, body, write_config
from fastapi.testclient import TestClient
from graph_testkit import ANSWER, ScriptedController, tool_action

from axon_ai.bootstrap.wiring import platform
from axon_ai.capabilities.api import FENCE_INSTRUCTION
from axon_ai.graph.domain.budget import is_tool_result
from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from axon_ai.mcp.ports import RemotePart, RemoteResult, RemoteTool

pytestmark = pytest.mark.us2

ECO = RemoteTool(
    name="eco",
    description="Devolve o texto recebido.",
    input_schema={"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]},
)

CONTROLLER_PROGRAMADO = AGENTIC_ASSISTANTS_YAML.replace(
    '      controller: ollama/qwen3:1.7b\n      allow: ["ollama/*"]\n  perdido:',
    '      controller: ctrl/controlador\n      allow: ["ollama/*", "ctrl/*"]\n  perdido:',
)
"""`pesquisador` (`flow: agentic`, `packs: [generic]`, `mcp: [demo]`) com o controller no provider `ctrl`."""

RESULTADO = "eco: olá do mcp"
SERVIDOR = ScriptedServer(tools=(ECO,), results={"eco": RemoteResult(parts=(RemotePart(kind="text", text=RESULTADO),))})


def _tools_offered(call: dict[str, Any]) -> set[str]:
    """Os nomes das tools que o `response_format` do controller oferece, um ramo por tool."""
    branches = call["response_format"]["json_schema"]["schema"]["anyOf"]
    return {branch["properties"]["name"]["const"] for branch in branches if "name" in branch["properties"]}


def test_assistant_generico_usa_o_resultado_do_mcp(tmp_path: Path) -> None:
    assert "controller: ctrl/controlador" in CONTROLLER_PROGRAMADO
    transporte = ScriptedMcpTransport({DEMO_ENDPOINT: SERVIDOR})
    controller = ScriptedController([tool_action("demo.eco", texto="olá do mcp"), ANSWER])
    geracao = ScriptedProvider(name="ollama", deltas=("Pronto.",))
    settings = write_config(tmp_path, assistants=CONTROLLER_PROGRAMADO, mcp=MCP_YAML)
    plataforma = platform(
        config=MemoryConfig(settings),
        overrides={
            "providers": {"ollama": geracao, "ctrl": controller},
            "mcp_transports": {"http": transporte, "sse": transporte, "stdio": transporte},
        },
    )
    assert plataforma.ok, plataforma.report.render()

    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="pesquisador"))

    assert response.status_code == 200, response.text

    # Pack e MCP no mesmo catálogo do controller.
    assert {"generic.calculate", "demo.eco"} <= _tools_offered(controller.calls[0])

    # A geração recebe o prompt do pack (pelo seam da 002), a instrução de cerca e o resultado cercado do MCP.
    assert plataforma.packs is not None
    prompts = list(plataforma.packs.system_prompts(plataforma.packs.compose(["generic"])))
    assert prompts and all(prompt.strip() for prompt in prompts)
    mensagens = geracao.calls[-1]["messages"]
    sistema = [mensagem["content"] for mensagem in mensagens if mensagem["role"] == "system"]
    assert sistema[: len(prompts)] == prompts
    assert FENCE_INSTRUCTION in sistema
    resultados = [mensagem["content"] or "" for mensagem in mensagens if is_tool_result(mensagem)]
    assert any("<tool_result" in resultado and RESULTADO in resultado for resultado in resultados), resultados
