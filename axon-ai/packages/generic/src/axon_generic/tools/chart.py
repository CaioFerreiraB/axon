"""Gráfico a partir de dados (spec 010, FR-013; ADR-052; research R28).

A tool só valida e entrega dados: monta o `Chart` do contrato 001, que a plataforma desenha para o usuário (no Open
WebUI, um gráfico interativo). Nenhum HTML sai daqui. Os dados vêm do modelo, logo são não-confiáveis (princípio VI):
o `Chart` limpa os textos e confere a forma na construção, e o erro volta legível para o controller corrigir. Módulo
puro — sem I/O, sem relógio, sem aleatoriedade.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from axon_ai_contracts import (
    CHART_MAX_POINTS,
    CHART_MAX_SERIES,
    Chart,
    ChartPoint,
    ChartSeries,
    JSONValue,
    ToolInvocation,
    ToolResult,
    ToolSpec,
)

INVALID: Final = "gráfico inválido"

DESCRIPTION: Final = (
    "Desenha um gráfico interativo para o usuário a partir de dados: linha, área, barras (simples ou empilhadas), "
    "dispersão, pizza ou rosca. Use quando o usuário pedir um gráfico ou uma visualização de valores que você já "
    f"tem. Passe os números já calculados e agregados (até {CHART_MAX_SERIES} séries e {CHART_MAX_POINTS} pontos no "
    "total); em série temporal, x é a data ISO (2026-10-28) com x_type 'temporal'; em pizza e rosca, uma série só, "
    "com uma fatia por ponto. Uma série por grandeza — não repita os mesmos valores em duas séries; a unidade "
    "(R$, %, kg) vai em unit. Chame uma vez por gráfico: ele aparece para o usuário assim que é criado, com a tabela "
    "dos dados, e não pode ser desfeito."
)

_TEXT: Final[Mapping[str, JSONValue]] = {"type": "string"}

PARAMETERS: Final[Mapping[str, JSONValue]] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["line", "area", "bar", "stacked_bar", "scatter", "pie", "donut"]},
        "title": _TEXT,
        "subtitle": _TEXT,
        "x_type": {
            "type": "string",
            "enum": ["temporal", "quantitative", "nominal"],
            "description": "temporal quando x é data ISO; quantitative quando x é número; nominal para categorias",
        },
        "x_label": _TEXT,
        "y_label": _TEXT,
        "unit": {"type": "string", "description": "unidade dos valores de y, como 'R$', '%' ou 'kg'"},
        "unit_position": {"type": "string", "enum": ["prefix", "suffix"]},
        "series": {
            "type": "array",
            "minItems": 1,
            "maxItems": CHART_MAX_SERIES,
            "items": {
                "type": "object",
                "properties": {
                    "name": _TEXT,
                    "points": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"anyOf": [{"type": "string"}, {"type": "number"}]},
                                "y": {"type": "number"},
                            },
                            "required": ["x", "y"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["name", "points"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["kind", "title", "series"],
    "additionalProperties": False,
}
"""No subconjunto estrito do controller (005 R23, 006 ADR-023): objetos fechados, sem `$ref` nem regex. Os
opcionais podem chegar ausentes ou nulos."""

_OPTIONAL: Final = ("subtitle", "x_label", "y_label", "unit")
_ISO_DATE: Final = re.compile(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")


async def chart(invocation: ToolInvocation) -> ToolResult:
    """Handler: `ToolResult` com o gráfico em `charts` e um resumo curto em `content`; erro legível em `error`.

    Não usa `request_id` nem `reference_time`: o resultado depende só dos argumentos.
    """
    try:
        built = build_chart(invocation.arguments)
    except KeyError as error:
        return ToolResult(content="", error=f"{INVALID}: falta o campo {error}")
    except (TypeError, ValueError) as error:
        return ToolResult(content="", error=f"{INVALID}: {error}")
    points = sum(len(item.points) for item in built.series)
    return ToolResult(
        content=(
            f"gráfico {built.id} criado e já mostrado ao usuário "
            f"({built.kind}, {len(built.series)} série(s), {points} ponto(s))"
        ),
        charts=(built,),
    )


def build_chart(arguments: Mapping[str, Any]) -> Chart:
    """Os argumentos (já validados pelo esquema no gateway) viram o `Chart`; o contrato confere o resto."""
    options: dict[str, Any] = {name: arguments[name] for name in _OPTIONAL if arguments.get(name) is not None}
    series = tuple(_series(item) for item in _items(arguments["series"], "series"))
    options["unit_position"] = arguments.get("unit_position") or "suffix"
    options["x_type"] = arguments.get("x_type") or _inferred_x_type(arguments["kind"], series)
    return Chart(kind=arguments["kind"], title=arguments["title"], series=series, **options)


def _inferred_x_type(kind: object, series: Sequence[ChartSeries]) -> str:
    """Sem `x_type`, o eixo é temporal quando todo x é data ISO (modelo pequeno costuma omitir o campo), numérico
    quando todo x é número, e de categorias no resto — inclusive em pizza e rosca."""
    xs = [point.x for item in series for point in item.points]
    if kind in ("pie", "donut") or not xs:
        return "nominal"
    if all(isinstance(x, float) for x in xs):
        return "quantitative"
    if all(isinstance(x, str) and _ISO_DATE.fullmatch(x) for x in xs):
        return "temporal"
    return "nominal"


def _series(item: Mapping[str, Any]) -> ChartSeries:
    points = tuple(ChartPoint(x=point["x"], y=point["y"]) for point in _items(item["points"], "points"))
    return ChartSeries(name=item["name"], points=points)


def _items(value: object, name: str) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise TypeError(f"{name} precisa ser uma lista")
    if not all(isinstance(item, Mapping) for item in value):
        raise TypeError(f"cada item de {name} precisa ser um objeto")
    return [item for item in value if isinstance(item, Mapping)]


def chart_spec() -> ToolSpec:
    """Especificação da tool nativa. O core aplica o namespace `generic.chart`."""
    return ToolSpec(
        name="chart",
        description=DESCRIPTION,
        parameters=PARAMETERS,
        kind="native",
        mutates=False,
        handler=chart,
    )
