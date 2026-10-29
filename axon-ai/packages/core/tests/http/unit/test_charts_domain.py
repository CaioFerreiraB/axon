"""O gráfico na resposta: tabela, opção do ECharts e página do iframe (FR-005c, ADR-052, research R62). Puro."""

from __future__ import annotations

import json
import re

from axon_ai.http.domain.charts import (
    OTHERS,
    SERIES_DARK,
    SERIES_LIGHT,
    ChartScripts,
    ScriptRef,
    chart_json,
    charts_table,
    echarts_option,
    embed_html,
    embeds_event,
    script_json,
)
from axon_ai_contracts import Chart, ChartPoint, ChartSeries

SCRIPTS = ChartScripts(
    echarts=ScriptRef(url="https://axon.example/static/echarts/6.1.0/echarts.min.js", integrity="sha384-a"),
    locale=ScriptRef(url="https://axon.example/static/echarts/6.1.0/langPT-br.js", integrity="sha384-b"),
    renderer=ScriptRef(url="https://axon.example/static/charts/abc/axon-chart.js", integrity="sha384-c"),
)


def serie(name: str, values: dict[str, float]) -> ChartSeries:
    return ChartSeries(name=name, points=tuple(ChartPoint(x=x, y=y) for x, y in values.items()))


def rosca(values: dict[str, float], **extra: object) -> Chart:
    return Chart(kind="donut", title="Gastos", series=(serie("Gastos", values),), **extra)  # type: ignore[arg-type]


def test_oito_cores_na_ordem_da_marca() -> None:
    assert len(SERIES_LIGHT) == len(SERIES_DARK) == 8
    assert SERIES_LIGHT[:4] == ("#2a78d6", "#eb6834", "#1baf7a", "#eda100"), "as quatro da marca primeiro"


# --- tabela ---------------------------------------------------------------------------------------------------------


def test_tabela_em_details_com_numeros_em_pt_br_e_unidade() -> None:
    chart = rosca({"Moradia": 2100, "Mercado": 1250.5}, unit="R$", unit_position="prefix")
    assert charts_table([chart]) == (
        "\n\n<details>\n<summary>Dados do gráfico: Gastos</summary>\n\n"
        "| Categoria | Gastos |\n| --- | --- |\n| Moradia | R$ 2.100 |\n| Mercado | R$ 1.250,5 |\n\n</details>"
    )


def test_tabela_junta_as_categorias_das_series_e_deixa_vazio_o_que_falta() -> None:
    chart = Chart(
        kind="bar",
        title="Tokens",
        x_label="Mês",
        series=(serie("Entrada", {"jul": 1, "ago": 2}), serie("Saída", {"ago": 3, "set": 4})),
    )
    linhas = charts_table([chart]).split("\n")
    assert "| Mês | Entrada | Saída |" in linhas
    assert "| jul | 1 |  |" in linhas and "| set |  | 4 |" in linhas


def test_tabela_escapa_o_que_vem_de_fora() -> None:
    chart = rosca({"a|b <i>": 1}, unit="%")
    chart = Chart(kind="donut", title="</summary><img src=x onerror=1>", series=chart.series)
    tabela = charts_table([chart])
    assert "<img" not in tabela and "&lt;img src=x onerror=1&gt;" in tabela
    assert "| a\\|b &lt;i&gt; |" in tabela


def test_dispersao_tem_uma_linha_por_ponto() -> None:
    pontos = ChartSeries(name="A", points=(ChartPoint(x=1.5, y=2), ChartPoint(x=1.5, y=3)))
    chart = Chart(kind="scatter", title="t", x_type="quantitative", series=(pontos,))
    assert "| Série | x | y |" in charts_table([chart]) and "| A | 1,5 | 3 |" in charts_table([chart])


def test_sem_grafico_sem_tabela() -> None:
    assert charts_table([]) == ""


# --- opção do ECharts -----------------------------------------------------------------------------------------------


def test_rosca_e_pizza_sem_legenda_com_rotulo() -> None:
    option = echarts_option(rosca({"a": 1, "b": 2}))
    assert "legend" not in option
    [series] = option["series"]
    assert series["type"] == "pie" and series["radius"] == ["45%", "70%"] and series["label"]["show"] is True
    pizza = echarts_option(Chart(kind="pie", title="t", series=(serie("s", {"a": 1}),)))
    assert pizza["series"][0]["radius"] == ["0%", "70%"]


def test_mais_de_oito_fatias_viram_sete_e_outros() -> None:
    valores = {f"c{i}": float(i) for i in range(1, 11)}
    data = echarts_option(rosca(valores))["series"][0]["data"]
    assert len(data) == 8 and data[-1] == {"name": OTHERS, "value": 1 + 2 + 3.0}
    assert [item["name"] for item in data[:7]] == ["c10", "c9", "c8", "c7", "c6", "c5", "c4"]
    assert "| c1 | 1 |" in charts_table([rosca(valores)]), "a tabela tem todas as fatias"


def test_linhas_categoricas_alinhadas_pela_uniao() -> None:
    chart = Chart(kind="line", title="t", series=(serie("a", {"x": 1, "y": 2}), serie("b", {"y": 3, "z": 4})))
    option = echarts_option(chart)
    assert option["xAxis"] == {"type": "category", "boundaryGap": False, "data": ["x", "y", "z"]}
    assert [s["data"] for s in option["series"]] == [[1.0, 2.0, None], [None, 3.0, 4.0]]
    assert option["legend"]["top"] == 0 and option["tooltip"]["trigger"] == "axis"


def test_serie_temporal_longa_ganha_zoom() -> None:
    dias = {f"2026-01-{d:02d}": float(d) for d in range(1, 32)}
    option = echarts_option(Chart(kind="area", title="t", x_type="temporal", series=(serie("a", dias),)))
    assert option["xAxis"]["type"] == "time" and option["series"][0]["data"][0] == ["2026-01-01", 1.0]
    assert option["series"][0]["areaStyle"] == {"opacity": 0.12}
    assert [z["type"] for z in option["dataZoom"]] == ["inside", "slider"]
    curta = {f"2026-01-{d:02d}": float(d) for d in range(1, 31)}
    assert "dataZoom" not in echarts_option(
        Chart(kind="line", title="t", x_type="temporal", series=(serie("a", curta),))
    )


def test_cinco_series_ou_mais_nao_dependem_so_da_cor() -> None:
    quatro = tuple(serie(f"s{i}", {"a": 1, "b": 2}) for i in range(4))
    cinco = tuple(serie(f"s{i}", {"a": 1, "b": 2}) for i in range(5))
    assert all("endLabel" not in s for s in echarts_option(Chart(kind="line", title="t", series=quatro))["series"])
    linhas = echarts_option(Chart(kind="line", title="t", series=cinco))
    assert all(s["endLabel"] == {"show": True, "formatter": "{a}"} for s in linhas["series"])
    assert all(s["labelLayout"] == {"moveOverlap": "shiftY"} for s in linhas["series"])
    pontos = tuple(ChartSeries(name=f"s{i}", points=(ChartPoint(x=1.0, y=1.0),)) for i in range(5))
    dispersao = echarts_option(Chart(kind="scatter", title="t", x_type="quantitative", series=pontos))
    assert [s["symbol"] for s in dispersao["series"]] == ["circle", "rect", "triangle", "diamond", "emptyCircle"]
    assert dispersao["tooltip"]["trigger"] == "item"


def test_barras_finas_e_empilhadas() -> None:
    chart = Chart(kind="stacked_bar", title="t", series=(serie("a", {"x": 1}), serie("b", {"x": 2})))
    option = echarts_option(chart)
    assert all(s["stack"] == "total" and s["barMaxWidth"] == 24 for s in option["series"])
    barra = echarts_option(Chart(kind="bar", title="t", series=(serie("a", {"x": 1}),)))
    assert barra["series"][0]["itemStyle"]["borderRadius"] == [4, 4, 0, 0] and "legend" not in barra


# --- página e evento ------------------------------------------------------------------------------------------------


def test_pagina_sem_script_inline_e_com_os_scripts_da_plataforma() -> None:
    page = embed_html(rosca({"a": 1}), SCRIPTS)
    tags = re.findall(r"<script[^>]*>", page)
    assert tags == [
        '<script src="https://axon.example/static/echarts/6.1.0/echarts.min.js" integrity="sha384-a" '
        'crossorigin="anonymous">',
        '<script src="https://axon.example/static/echarts/6.1.0/langPT-br.js" integrity="sha384-b" '
        'crossorigin="anonymous">',
        '<script type="application/json" id="axon-chart">',
        '<script src="https://axon.example/static/charts/abc/axon-chart.js" integrity="sha384-c" '
        'crossorigin="anonymous">',
    ]
    spec = json.loads(page.split('id="axon-chart">', 1)[1].split("</script>", 1)[0])
    assert spec["title"] == "Gastos" and spec["option"]["series"][0]["type"] == "pie"
    assert spec["themes"]["dark"]["series"] == list(SERIES_DARK)


def test_titulo_hostil_nao_sai_do_bloco_de_dados() -> None:
    chart = Chart(kind="donut", title='</script><script>alert(1)</script>"', series=(serie("a", {"x": 1}),))
    page = embed_html(chart, SCRIPTS)
    assert page.count("</script>") == 4 and "alert(1)</script>" not in page
    assert "\\u003c/script\\u003e" in page


def test_script_json_escapa_o_que_fecharia_a_tag() -> None:
    assert script_json({"t": "<a>&\u2028\u2029"}) == '{"t":"\\u003ca\\u003e\\u0026\\u2028\\u2029"}'


def test_um_evento_embeds_com_todos_os_graficos() -> None:
    um, outro = rosca({"a": 1}), rosca({"b": 1})
    event = embeds_event([um, outro], SCRIPTS)
    assert event["type"] == "embeds" and event["data"]["replace"] is True
    assert len(event["data"]["embeds"]) == 2 and all(e.startswith("<!doctype html>") for e in event["data"]["embeds"])


def test_json_neutro_do_x_axon() -> None:
    chart = rosca({"a": 1}, unit="R$", unit_position="prefix")
    assert chart_json(chart) == {
        "id": chart.id,
        "kind": "donut",
        "title": "Gastos",
        "subtitle": None,
        "x_type": "nominal",
        "x_label": None,
        "y_label": None,
        "unit": "R$",
        "unit_position": "prefix",
        "series": [{"name": "Gastos", "points": [{"x": "a", "y": 1.0}]}],
    }
