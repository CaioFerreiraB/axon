"""Gráficos na resposta (FR-005c, ADR-052, research R62). Puro.

A API é a única a escrever HTML de gráfico, sempre a partir do `Chart` do contrato 001 — dados de um esquema fechado.
Daqui saem três formas do mesmo gráfico:

- a **tabela** em `<details>`, que vai sempre no texto da resposta (acessibilidade, clientes sem `embeds` e o histórico
  que o modelo lê no turno seguinte);
- a **página** do iframe do Open WebUI (evento `embeds`), com o ECharts servido pela própria plataforma;
- o **JSON** neutro de `x_axon.charts`, para outros clientes desenharem como quiserem.

Na página, o que vem do `Chart` entra só como dado: o JSON embutido escapa `<`, `>`, `&`, U+2028 e U+2029, os textos
vão ao DOM por `textContent`, e a dica é montada por código fixo que escapa cada nome. Os formatadores são código da
página, nunca texto da entrada.
"""

from __future__ import annotations

import html
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from axon_ai_contracts import Chart, ChartSeries

ECHARTS_VERSION: Final = "6.1.0"
"""Versão vendorizada em `http/adapters/static/echarts/<versão>/`, servida em `/static/echarts/<versão>/`."""

SERIES_LIGHT: Final = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SERIES_DARK: Final = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")
"""As oito cores de série, nesta ordem (ADR-052, item 3): as quatro da marca e as quatro da paleta de referência,
validadas entre vizinhas nos dois temas. A cor segue a posição da série, nunca a grandeza."""

OTHERS: Final = "Outros"
_ROUND = frozenset({"pie", "donut"})
_CARTESIAN_AXIS = frozenset({"line", "area", "bar", "stacked_bar"})
_ZOOM_FROM = 30
"""Acima desta quantidade de pontos numa série, o eixo temporal ou numérico ganha o `dataZoom` (slider e roda)."""
_LABELED_FROM = 5
"""A partir de cinco séries, linha e área levam o nome na ponta e a dispersão uma forma por série: entre todos os
pares, as cores 5 a 8 não se distinguem bem só pela cor (ADR-052, Contexto)."""
_SYMBOLS: Final = (
    "circle",
    "rect",
    "triangle",
    "diamond",
    "emptyCircle",
    "emptyRect",
    "emptyTriangle",
    "emptyDiamond",
)
_X_HEADERS: Final = {"temporal": "Data", "quantitative": "x", "nominal": "Categoria"}


@dataclass(frozen=True, slots=True, kw_only=True)
class ScriptRef:
    """Um script da página do gráfico: endereço absoluto e a integridade (`sha384-…`) que o navegador confere."""

    url: str
    integrity: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ChartScripts:
    """O ECharts, o locale pt-BR e o desenhista da plataforma (`axon-chart.js`), servidos por ela mesma (ADR-052,
    item 6). Montado na fábrica da app; a página do gráfico não tem script inline."""

    echarts: ScriptRef
    locale: ScriptRef
    renderer: ScriptRef


# --- JSON neutro ----------------------------------------------------------------------------------------------------


def chart_json(chart: Chart) -> dict[str, Any]:
    """O `Chart` em JSON, como está no contrato: o que `x_axon.charts` leva (ADR-052, item 5)."""
    return {
        "id": chart.id,
        "kind": chart.kind,
        "title": chart.title,
        "subtitle": chart.subtitle,
        "x_type": chart.x_type,
        "x_label": chart.x_label,
        "y_label": chart.y_label,
        "unit": chart.unit,
        "unit_position": chart.unit_position,
        "series": [
            {"name": item.name, "points": [{"x": point.x, "y": point.y} for point in item.points]}
            for item in chart.series
        ],
    }


# --- tabela ---------------------------------------------------------------------------------------------------------


def charts_table(charts: Sequence[Chart]) -> str:
    """Um bloco `<details>` por gráfico, com a tabela dos dados em markdown, para vir depois do texto da resposta.

    A pizza e a rosca listam todas as fatias, inclusive as que o desenho junta em "Outros". O Open WebUI desenha o
    bloco recolhido e o devolve no histórico (só os `<details>` com `type` saem).
    """
    return "".join(_table(chart) for chart in charts)


def _table(chart: Chart) -> str:
    header, rows = _rows(chart)
    lines = [
        "| " + " | ".join(_cell(item) for item in header) + " |",
        "|" + "|".join(" --- " for _ in header) + "|",
        *("| " + " | ".join(_cell(item) for item in row) + " |" for row in rows),
    ]
    summary = html.escape(f"Dados do gráfico: {chart.title}", quote=False)
    return f"\n\n<details>\n<summary>{summary}</summary>\n\n" + "\n".join(lines) + "\n\n</details>"


def _rows(chart: Chart) -> tuple[list[str], list[list[str]]]:
    x_header = chart.x_label or _X_HEADERS[chart.x_type]
    if chart.kind == "scatter":
        header = ["Série", x_header, chart.y_label or "y"]
        rows = [[item.name, _x_text(point.x), _value(chart, point.y)] for item in chart.series for point in item.points]
        return header, rows
    header = [x_header, *(item.name for item in chart.series)]
    by_series = [{point.x: point.y for point in item.points} for item in chart.series]
    rows = [
        [_x_text(x), *(_value(chart, values[x]) if x in values else "" for values in by_series)]
        for x in _xs(chart.series)
    ]
    return header, rows


def _cell(text: str) -> str:
    """Escapa o que fecharia a célula ou viraria HTML: o texto do `Chart` é dado não confiável."""
    return html.escape(text, quote=False).replace("|", "\\|")


def _x_text(x: str | float) -> str:
    return x if isinstance(x, str) else _number(x)


def _value(chart: Chart, value: float) -> str:
    text = _number(value)
    if chart.unit is None:
        return text
    return f"{chart.unit} {text}" if chart.unit_position == "prefix" else f"{text} {chart.unit}"


def _number(value: float) -> str:
    """Número em pt-BR, até duas casas, sem zeros à direita: 1250.5 → "1.250,5"; 2100.0 → "2.100"."""
    if value.is_integer() and abs(value) < 1e15:
        text = f"{int(value):,}"
    else:
        text = f"{value:,.2f}".rstrip("0").rstrip(".")
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _xs(series: Sequence[ChartSeries]) -> list[str | float]:
    """Os valores de x na ordem em que aparecem pela primeira vez, juntando as séries."""
    seen: dict[str | float, None] = {}
    for item in series:
        for point in item.points:
            seen.setdefault(point.x, None)
    return list(seen)


# --- opção do ECharts -----------------------------------------------------------------------------------------------


def echarts_option(chart: Chart) -> dict[str, Any]:
    """A opção do ECharts, sem cores nem formatadores — a página os aplica conforme o tema (ADR-052, item 3)."""
    if chart.kind in _ROUND:
        return _round_option(chart)
    return _cartesian_option(chart)


def _round_option(chart: Chart) -> dict[str, Any]:
    """Pizza e rosca: rótulo em cada fatia e nenhuma legenda; acima de oito fatias, as sete maiores e "Outros"."""
    [series] = chart.series
    points = [{"name": point.x, "value": point.y} for point in series.points]
    if len(points) > len(SERIES_LIGHT):
        ordered = sorted(points, key=lambda item: -float(item["value"]))
        kept = ordered[: len(SERIES_LIGHT) - 1]
        rest = sum(float(item["value"]) for item in ordered[len(SERIES_LIGHT) - 1 :])
        points = [*kept, {"name": OTHERS, "value": rest}]
    return {
        "tooltip": {"trigger": "item"},
        "series": [
            {
                "type": "pie",
                "name": series.name,
                "radius": ["45%", "70%"] if chart.kind == "donut" else ["0%", "70%"],
                "center": ["50%", "50%"],
                "padAngle": 1,
                "itemStyle": {"borderRadius": 4, "borderWidth": 2},
                "label": {"show": True},
                "emphasis": {"scale": True, "scaleSize": 4},
                "data": points,
            }
        ],
    }


def _cartesian_option(chart: Chart) -> dict[str, Any]:
    many = len(chart.series) >= _LABELED_FROM
    x_axis_type = {"temporal": "time", "quantitative": "value", "nominal": "category"}[chart.x_type]
    legend = len(chart.series) > 1
    zoom = x_axis_type != "category" and max(len(item.points) for item in chart.series) > _ZOOM_FROM
    labeled_lines = many and chart.kind in ("line", "area")
    x_axis: dict[str, Any] = {"type": x_axis_type, "boundaryGap": chart.kind in ("bar", "stacked_bar")}
    categories: list[str | float] | None = None
    if x_axis_type == "category":
        categories = _xs(chart.series)
        x_axis["data"] = categories
    if chart.x_label:
        x_axis |= {"name": chart.x_label, "nameLocation": "middle", "nameGap": 28}
    y_axis: dict[str, Any] = {"type": "value"}
    if chart.y_label:
        y_axis |= {"name": chart.y_label, "nameLocation": "end", "nameGap": 12}
    option: dict[str, Any] = {
        "tooltip": {"trigger": "axis" if chart.kind in _CARTESIAN_AXIS else "item"},
        "grid": {
            "left": 8,
            "right": 96 if labeled_lines else 16,
            "top": (32 if legend else 12) + (20 if chart.y_label else 0),
            "bottom": (40 if zoom else 8) + (20 if chart.x_label else 0),
            "containLabel": True,
        },
        "xAxis": x_axis,
        "yAxis": y_axis,
        "series": [_series(chart, index, item, categories) for index, item in enumerate(chart.series)],
    }
    if legend:
        option["legend"] = {"type": "scroll", "top": 0, "left": 0}
    if zoom:
        option["dataZoom"] = [{"type": "inside"}, {"type": "slider", "height": 20, "bottom": 6}]
    return option


def _series(chart: Chart, index: int, series: ChartSeries, categories: list[str | float] | None) -> dict[str, Any]:
    if categories is not None:
        values = {point.x: point.y for point in series.points}
        data: list[Any] = [values.get(x) for x in categories]
    else:
        data = [[point.x, point.y] for point in series.points]
    item: dict[str, Any] = {"name": series.name, "data": data}
    many = len(chart.series) >= _LABELED_FROM
    if chart.kind in ("line", "area"):
        item |= {"type": "line", "showSymbol": False, "symbolSize": 8, "lineStyle": {"width": 2}, "connectNulls": True}
        if chart.kind == "area":
            item["areaStyle"] = {"opacity": 0.12}
        if many:
            # Rótulo na ponta, afastado do vizinho quando as linhas terminam perto.
            item["endLabel"] = {"show": True, "formatter": "{a}"}
            item["labelLayout"] = {"moveOverlap": "shiftY"}
    elif chart.kind == "bar":
        item |= {"type": "bar", "barMaxWidth": 24, "itemStyle": {"borderRadius": [4, 4, 0, 0]}}
    elif chart.kind == "stacked_bar":
        item |= {"type": "bar", "stack": "total", "barMaxWidth": 24, "itemStyle": {"borderWidth": 1}}
    else:
        item |= {"type": "scatter", "symbolSize": 10, "symbol": _SYMBOLS[index] if many else "circle"}
    return item


# --- página do iframe -----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _Theme:
    surface: str
    text: str
    text2: str
    text3: str
    grid: str
    border: str
    tooltip: str
    series: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "text": self.text,
            "text2": self.text2,
            "text3": self.text3,
            "grid": self.grid,
            "border": self.border,
            "tooltip": self.tooltip,
            "series": list(self.series),
        }


_LIGHT = _Theme(
    surface="#ffffff",
    text="#111827",
    text2="#556070",
    text3="#666d7c",
    grid="#e5e7eb",
    border="#d1d5db",
    tooltip="#ffffff",
    series=SERIES_LIGHT,
)
_DARK = _Theme(
    surface="#171717",
    text="#f1f3f7",
    text2="#a3abbb",
    text3="#8c94a6",
    grid="#2e2e2e",
    border="#404040",
    tooltip="#262626",
    series=SERIES_DARK,
)


def embed_html(chart: Chart, scripts: ChartScripts) -> str:
    """A página de um gráfico para o iframe `srcdoc` do Open WebUI (sem `allow-same-origin`).

    Só dados e referências: a especificação vai num `<script type="application/json">`, que o navegador não executa,
    e o desenho é do `axon-chart.js` da plataforma, com `integrity` — nenhum script inline. O tema segue
    `prefers-color-scheme`, e a altura vai ao pai por `postMessage`.
    """
    spec = {
        "id": chart.id,
        "kind": chart.kind,
        "title": chart.title,
        "subtitle": chart.subtitle,
        "temporal": chart.x_type == "temporal",
        "unit": chart.unit,
        "prefix": chart.unit_position == "prefix",
        "height": 320 if chart.kind in _ROUND else 300,
        "option": echarts_option(chart),
        "themes": {"light": _LIGHT.as_json(), "dark": _DARK.as_json()},
    }
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>{_STYLE}</style>{_script(scripts.echarts)}{_script(scripts.locale)}</head><body>"
        '<div class="c"><h3 id="t"></h3><p id="s"></p><div id="plot" role="img"></div></div>'
        f'<script type="application/json" id="axon-chart">{script_json(spec)}</script>'
        f"{_script(scripts.renderer)}</body></html>"
    )


def _script(ref: ScriptRef) -> str:
    return (
        f'<script src="{html.escape(ref.url)}" integrity="{html.escape(ref.integrity)}" crossorigin="anonymous">'
        "</script>"
    )


def embeds_event(charts: Sequence[Chart], scripts: ChartScripts) -> dict[str, Any]:
    """Um evento `embeds` com todos os gráficos: no Open WebUI v0.12, cada evento substitui a lista na tela, e o
    `replace` faz o banco guardar a mesma lista, na mesma ordem (ADR-052, item 4)."""
    return {"type": "embeds", "data": {"embeds": [embed_html(chart, scripts) for chart in charts], "replace": True}}


def script_json(value: object) -> str:
    """JSON que pode ir dentro de `<script>`: nada fecha a tag, abre comentário nem quebra a linha do JavaScript."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    for raw, escaped in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        text = text.replace(raw, escaped)
    return text


_STYLE: Final = (
    # Sem `color-scheme`: o Open WebUI não o declara, e um iframe com esquema diferente do da página ganha fundo opaco
    # no Chrome. O tema vem do `prefers-color-scheme`, que não depende dele.
    ':root{font-family:"Mona Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}'
    "html,body{margin:0;background:transparent}.c{padding:4px 2px 0}"
    f"h3{{margin:0 0 2px;font-size:.9375rem;font-weight:600;color:{_LIGHT.text}}}"
    f"p{{margin:0 0 8px;font-size:.75rem;color:{_LIGHT.text2}}}#plot{{width:100%}}"
    f"@media (prefers-color-scheme:dark){{h3{{color:{_DARK.text}}}p{{color:{_DARK.text2}}}}}"
)
