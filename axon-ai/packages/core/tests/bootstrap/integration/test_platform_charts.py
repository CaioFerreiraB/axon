"""ADR-052 ponta a ponta, no perfil `test` e sem rede (011 FR-030; research R57).

Uma tool MCP programada devolve uma série em JSON; o controller pede `generic.chart` com os números; a resposta em
streaming leva a tabela em `<details>`, um evento `embeds` do Open WebUI com a página do gráfico — cujos scripts a
própria plataforma serve — e o `Chart` em `x_axon.charts`. Só o controller e o servidor MCP são programados; o resto
é a plataforma de verdade, com o `axon-generic` carregado pelo entry point.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bootstrap_testkit import AGENTIC_ASSISTANTS_YAML, DEMO_ENDPOINT, MCP_YAML, MODEL, OIDC, MemoryConfig, write_config
from fastapi.testclient import TestClient
from graph_testkit import ANSWER, ScriptedController, tool_action

from axon_ai.bootstrap.wiring import platform
from axon_ai.graph.domain.images import CHARTS_INSTRUCTION
from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from axon_ai.mcp.ports import RemotePart, RemoteResult, RemoteTool

BASE = "https://axon.example"
SERIE = RemoteTool(
    name="serie",
    description="Gastos por mês.",
    input_schema={"type": "object", "properties": {"ano": {"type": "string"}}, "required": ["ano"]},
)
DADOS = {"meses": [{"mes": "2026-08-01", "total": 3100}, {"mes": "2026-09-01", "total": 2875.5}]}
COM_CONTROLLER = AGENTIC_ASSISTANTS_YAML.replace(
    f'      controller: ollama/{MODEL}\n      allow: ["ollama/*"]',
    '      controller: ctrl/controlador\n      allow: ["ollama/*", "ctrl/*"]',
)
MCP_COM_SERIE = MCP_YAML.replace("[eco]", "[eco, serie]")
CABECALHOS = {**OIDC, "x-axon-store": "false", "x-axon-charts": "embeds"}


def chunks(text: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]


def test_dados_do_mcp_viram_grafico_no_open_webui(tmp_path: Path) -> None:
    resultado = RemoteResult(parts=(RemotePart(kind="text", text=json.dumps(DADOS)),))
    transporte = ScriptedMcpTransport({DEMO_ENDPOINT: ScriptedServer(tools=(SERIE,), results={"serie": resultado})})
    grafico = {
        "kind": "line",
        "title": "Gastos por mês",
        "x_type": "temporal",
        "unit": "R$",
        "unit_position": "prefix",
        "series": [{"name": "Total", "points": [{"x": m["mes"], "y": m["total"]} for m in DADOS["meses"]]}],
    }
    controller = ScriptedController(
        [tool_action("demo.serie", ano="2026"), tool_action("generic.chart", **grafico), ANSWER]
    )
    geracao = ScriptedProvider(name="ollama", deltas=("Os gastos caíram em setembro.",))
    settings = write_config(tmp_path, assistants=COM_CONTROLLER, mcp=MCP_COM_SERIE, charts_script_base_url=BASE)
    plataforma = platform(
        config=MemoryConfig(settings),
        overrides={"providers": {"ollama": geracao, "ctrl": controller}, "mcp_transports": {"http": transporte}},
    )
    assert plataforma.ok, plataforma.report.render()

    with TestClient(plataforma.app) as client:
        resposta = client.post(
            "/v1/chat/completions",
            headers=CABECALHOS,
            json={
                "model": "pesquisador",
                "messages": [{"role": "user", "content": "gráfico dos gastos"}],
                "stream": True,
            },
        )
        assert resposta.status_code == 200, resposta.text
        todos = chunks(resposta.text)
        texto = "".join(c["choices"][0]["delta"].get("content", "") for c in todos)
        assert texto.startswith("Os gastos caíram em setembro.\n\n<details>")
        assert "| 2026-08-01 | R$ 3.100 |" in texto and "| 2026-09-01 | R$ 2.875,5 |" in texto

        [evento] = [c["event"] for c in todos if "event" in c and c["event"]["type"] == "embeds"]
        [pagina] = evento["data"]["embeds"]
        scripts = re.findall(r'<script src="([^"]+)" integrity="([^"]+)"', pagina)
        assert scripts[0][0] == f"{BASE}/static/echarts/6.1.0/echarts.min.js"
        for url, _ in scripts:
            assert client.get(url.removeprefix(BASE)).status_code == 200, url
        [chart] = todos[-1]["x_axon"]["charts"]
        assert chart["kind"] == "line" and chart["series"][0]["points"][1] == {"x": "2026-09-01", "y": 2875.5}

    assert {"role": "system", "content": CHARTS_INSTRUCTION} in geracao.calls[-1]["messages"]
    resultado_do_grafico = controller.calls[-1]["messages"][-1]["content"]
    assert "[gráfico chart-" in resultado_do_grafico and "2875" not in resultado_do_grafico, "só a marca volta"
