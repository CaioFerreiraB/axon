"""Gráficos na resposta (FR-005c, ADR-052; research R62): a tabela no texto, `x_axon.charts`, o evento `embeds` do Open
WebUI atrás de `x-axon-charts` e o ECharts servido pela plataforma."""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi.testclient import TestClient
from http_testkit import StaticGrants, SurfaceRecordingAuthenticator, app_with, body, chunks_of

from axon_ai.graph.api import ExecutionEvent, FinalEvent, TokenEvent
from axon_ai.http.adapters.static import ASSETS, STATIC_DIR
from axon_ai_contracts import Chart, ChartPoint, ChartSeries

ROSCA = Chart(
    kind="donut",
    title="Gastos por categoria",
    unit="R$",
    unit_position="prefix",
    series=(ChartSeries(name="Gastos", points=(ChartPoint(x="Moradia", y=2100), ChartPoint(x="Mercado", y=1250))),),
)
BASE = "https://axon.example"


class ChartEngine:
    """Motor programado: um texto e o gráfico no evento final, como o `agentic` com a tool `generic.chart`."""

    def __init__(self, *charts: Chart) -> None:
        self.charts = charts

    def flows(self) -> tuple[str, ...]:
        return ("chat",)

    def flow_roles(self) -> Mapping[str, tuple[str, ...]]:
        return {"chat": ("generation",)}

    def run(self, grant: Any, request: Any) -> AsyncIterator[ExecutionEvent]:
        return self._run()

    async def _run(self) -> AsyncIterator[ExecutionEvent]:
        yield TokenEvent(text="Aqui está.")
        yield FinalEvent(answer="Aqui está.", charts=self.charts)


def client(*charts: Chart, base: str | None = BASE) -> TestClient:
    app = app_with(
        ChartEngine(*charts),
        authenticator=SurfaceRecordingAuthenticator(),
        grants=StaticGrants(),
        charts_base_url=base,
    )
    return TestClient(app)


def stream(test_client: TestClient, **headers: str) -> list[dict[str, Any]]:
    response = test_client.post("/v1/chat/completions", headers=headers, json=body(stream=True))
    assert response.status_code == 200
    return chunks_of(response.text)


def content(chunks: list[dict[str, Any]]) -> str:
    return "".join(c["choices"][0]["delta"].get("content", "") for c in chunks if c.get("choices"))


def test_com_embeds_sai_um_evento_depois_da_tabela_e_antes_do_fim() -> None:
    chunks = stream(client(ROSCA), **{"x-axon-charts": "embeds"})

    texto = content(chunks)
    assert texto.startswith("Aqui está.\n\n<details>\n<summary>Dados do gráfico: Gastos por categoria</summary>")
    assert "| Moradia | R$ 2.100 |" in texto
    eventos = [(i, c["event"]) for i, c in enumerate(chunks) if "event" in c]
    assert [e["type"] for _, e in eventos] == ["embeds"]
    [(posicao, evento)] = eventos
    assert chunks[posicao]["choices"][0]["delta"] == {}
    ultimo_texto = max(i for i, c in enumerate(chunks) if c["choices"][0]["delta"].get("content"))
    assert ultimo_texto < posicao < len(chunks) - 1, "depois da tabela e antes do chunk final"
    [pagina] = evento["data"]["embeds"]
    assert evento["data"]["replace"] is True
    assert f'src="{BASE}/static/echarts/6.1.0/echarts.min.js"' in pagina
    assert re.search(rf'src="{BASE}/static/charts/[0-9a-f]{{12}}/axon-chart.js"', pagina)
    assert chunks[-1]["x_axon"]["charts"][0]["id"] == ROSCA.id


def test_sem_o_cabecalho_so_a_tabela_e_o_x_axon() -> None:
    chunks = stream(client(ROSCA))
    assert not any("event" in c for c in chunks)
    assert "<details>" in content(chunks)
    assert chunks[-1]["x_axon"]["charts"][0]["series"][0]["points"][0] == {"x": "Moradia", "y": 2100.0}


def test_sem_endereco_da_plataforma_o_embeds_nao_sai() -> None:
    chunks = stream(client(ROSCA, base=None), **{"x-axon-charts": "embeds"})
    assert not any("event" in c for c in chunks) and "<details>" in content(chunks)


def test_sem_grafico_nada_muda() -> None:
    chunks = stream(client(), **{"x-axon-charts": "embeds"})
    assert content(chunks) == "Aqui está." and chunks[-1]["x_axon"]["charts"] == []


def test_dois_graficos_num_evento_so() -> None:
    outro = Chart(kind="bar", title="Outro", series=(ChartSeries(name="a", points=(ChartPoint(x="x", y=1),)),))
    chunks = stream(client(ROSCA, outro), **{"x-axon-charts": "embeds"})
    [evento] = [c["event"] for c in chunks if "event" in c]
    assert len(evento["data"]["embeds"]) == 2
    assert content(chunks).count("<details>") == 2


def test_sem_streaming_a_tabela_vai_no_conteudo() -> None:
    response = client(ROSCA).post("/v1/chat/completions", headers={"x-axon-charts": "embeds"}, json=body())
    assert response.status_code == 200
    message = response.json()["choices"][0]["message"]["content"]
    assert message.startswith("Aqui está.\n\n<details>") and "event" not in response.json()
    assert response.json()["x_axon"]["charts"][0]["kind"] == "donut"


def test_valor_desconhecido_do_cabecalho_e_400() -> None:
    response = client(ROSCA).post("/v1/chat/completions", headers={"x-axon-charts": "html"}, json=body())
    assert response.status_code == 400
    assert response.json()["error"]["param"] == "x-axon-charts"


def sri(data: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()


def test_rota_estatica_publica_imutavel_e_com_a_integridade_da_pagina() -> None:
    test_client = client(ROSCA)
    chunks = stream(test_client, **{"x-axon-charts": "embeds"})
    [pagina] = next(c["event"] for c in chunks if "event" in c)["data"]["embeds"]
    scripts = re.findall(r'<script src="([^"]+)" integrity="([^"]+)"', pagina)
    assert len(scripts) == 3
    for url, integrity in scripts:
        response = test_client.get(url.removeprefix(BASE))
        assert response.status_code == 200, url
        assert sri(response.content) == integrity
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert response.headers["access-control-allow-origin"] == "*"
        assert response.headers["content-type"].startswith("text/javascript")
    echarts = test_client.get("/static/echarts/6.1.0/echarts.min.js")
    assert echarts.content == (ASSETS / "echarts.min.js").read_bytes()
    assert test_client.get("/static/echarts/6.1.0/LICENSE").status_code == 200


def test_rota_estatica_recusa_o_que_nao_serve() -> None:
    test_client = client()
    assert test_client.get("/static/echarts/5.0.0/echarts.min.js").status_code == 404
    assert test_client.get("/static/echarts/6.1.0/../../adapters/static.py").status_code == 404
    assert test_client.get("/static/echarts/6.1.0/package.json").status_code == 404
    assert test_client.get("/static/charts/000000000000/axon-chart.js").status_code == 404
    assert (STATIC_DIR / "axon-chart.js").is_file()


def test_a_conversa_gravada_leva_a_tabela_para_o_turno_seguinte() -> None:
    test_client = client(ROSCA)
    response = test_client.post("/v1/chat/completions", json=body())
    conversation_id = response.json()["x_axon"]["conversation_id"]
    stored = test_client.get(f"/v1/conversations/{conversation_id}").json()
    resposta = stored["messages"][-1]
    assert resposta["role"] == "assistant"
    assert resposta["content"].startswith("Aqui está.\n\n<details>") and "| Mercado | R$ 1.250 |" in resposta["content"]
