"""ADR-044 ponta a ponta, no perfil `test` e sem rede (011 FR-029; research R56).

Uma tool MCP programada devolve texto e PNG; a resposta leva a imagem em markdown; no turno seguinte — com o histórico
devolvido pelo cliente, como o Open WebUI faz — o controller pede `view_image` e a imagem chega ao provider simulado da
geração. Só o controller e o servidor MCP são programados; o resto é a plataforma de verdade.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from bootstrap_testkit import AGENTIC_ASSISTANTS_YAML, DEMO_ENDPOINT, MCP_YAML, MODEL, OIDC, MemoryConfig, write_config
from fastapi.testclient import TestClient
from graph_testkit import ANSWER, ScriptedController, tool_action

from axon_ai.bootstrap.wiring import platform
from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from axon_ai.mcp.ports import RemotePart, RemoteResult, RemoteTool
from axon_ai_contracts import Attachment

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4
GRAFICO = RemoteTool(
    name="grafico",
    description="Gráfico de gastos.",
    input_schema={"type": "object", "properties": {"mes": {"type": "string"}}, "required": ["mes"]},
)
COM_VISAO = AGENTIC_ASSISTANTS_YAML.replace(
    f"    mcp: [demo]\n    models:\n      generation: ollama/{MODEL}\n      controller: ollama/{MODEL}\n"
    '      allow: ["ollama/*"]',
    f"    mcp: [demo]\n    allowed_tools: [demo.grafico]\n    models:\n"
    f"      generation: {{model: ollama/{MODEL}, vision: true}}\n      controller: ctrl/controlador\n"
    '      allow: ["ollama/*", "ctrl/*"]',
)
MCP_COM_GRAFICO = MCP_YAML.replace("[eco]", "[eco, grafico]")
EFEMERO = {**OIDC, "x-axon-store": "false"}


def test_imagem_da_tool_chega_ao_usuario_e_no_turno_seguinte_ao_modelo(tmp_path: Path) -> None:
    resultado = RemoteResult(
        parts=(
            RemotePart(kind="text", text="Alimentação: R$ 900"),
            RemotePart(kind="image", mime="image/png", data=PNG),
        )
    )
    transporte = ScriptedMcpTransport({DEMO_ENDPOINT: ScriptedServer(tools=(GRAFICO,), results={"grafico": resultado})})
    imagem = Attachment(mime="image/png", data=PNG)
    controller = ScriptedController(
        [
            tool_action("demo.grafico", mes="2026-10"),
            ANSWER,
            json.dumps({"action": "view_image", "id": imagem.id}),
            ANSWER,
        ]
    )
    geracao = ScriptedProvider(name="ollama", deltas=("Pronto.",))
    settings = write_config(tmp_path, assistants=COM_VISAO, mcp=MCP_COM_GRAFICO)
    plataforma = platform(
        config=MemoryConfig(settings),
        overrides={"providers": {"ollama": geracao, "ctrl": controller}, "mcp_transports": {"http": transporte}},
    )
    assert plataforma.ok, plataforma.report.render()

    with TestClient(plataforma.app) as client:
        pergunta = {"role": "user", "content": "gastos de outubro"}
        primeira = client.post(
            "/v1/chat/completions", headers=EFEMERO, json={"model": "pesquisador", "messages": [pergunta]}
        )
        assert primeira.status_code == 200, primeira.text
        resposta = primeira.json()["choices"][0]["message"]["content"]
        uri = f"data:image/png;base64,{base64.b64encode(PNG).decode()}"
        assert resposta == f"Pronto.\n\n![imagem]({uri})"
        assert primeira.json()["x_axon"]["attachments"] == [
            {"id": imagem.id, "mime": "image/png", "size_bytes": len(PNG)}
        ]
        assert geracao.images == [], "no turno em que nasce, a imagem não vai ao modelo"

        historico = [
            pergunta,
            {"role": "assistant", "content": resposta},
            {"role": "user", "content": "o que é aquele pico?"},
        ]
        segunda = client.post(
            "/v1/chat/completions", headers=EFEMERO, json={"model": "pesquisador", "messages": historico}
        )

    assert segunda.status_code == 200, segunda.text
    assert geracao.images == [uri]
    sistema = controller.calls[2]["messages"][0]["content"]
    assert imagem.id in sistema and "base64" not in json.dumps(controller.calls[2]["messages"])
    assert plataforma.trace is not None
    registros = plataforma.trace.trace(segunda.json()["x_axon"]["request_id"]).records
    decisoes = [dict(r.attributes) for r in registros if r.type == "controller_decision"]
    assert {"iteration": 1, "action": "view_image", "images": [imagem.id]} in decisoes
