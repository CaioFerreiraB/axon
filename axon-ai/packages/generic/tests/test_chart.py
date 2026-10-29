"""A tool `chart` (spec 010, FR-013; ADR-052; research R28): dados viram `Chart`, erro volta legível."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from axon_ai_contracts import CHART_MAX_SERIES, Chart
from axon_ai_contracts.testing import tool_invocation
from axon_generic.tools.chart import INVALID, PARAMETERS, build_chart, chart, chart_spec

ROSCA: dict[str, Any] = {
    "kind": "donut",
    "title": "Gastos por categoria",
    "unit": "R$",
    "unit_position": "prefix",
    "series": [{"name": "Gastos", "points": [{"x": "Moradia", "y": 2100}, {"x": "Mercado", "y": 1250.5}]}],
}


def run(arguments: dict[str, Any]) -> Any:
    return asyncio.run(chart(tool_invocation(arguments)))


def test_dados_viram_o_chart_do_contrato() -> None:
    result = run(ROSCA)
    [drawn] = result.charts
    assert isinstance(drawn, Chart) and result.error is None
    assert (drawn.kind, drawn.title) == ("donut", "Gastos por categoria")
    assert (drawn.unit, drawn.unit_position) == ("R$", "prefix")
    assert [point.x for point in drawn.series[0].points] == ["Moradia", "Mercado"]
    assert result.content == f"gráfico {drawn.id} criado e já mostrado ao usuário (donut, 1 série(s), 2 ponto(s))"


def test_opcionais_ausentes_ou_nulos_viram_o_padrao() -> None:
    """O adapter da OpenAI torna todo campo obrigatório e anulável (ADR-023): `null` vale como ausente."""
    nulos = ROSCA | {"x_type": None, "unit_position": None, "subtitle": None, "x_label": None}
    drawn = build_chart(nulos)
    assert (drawn.x_type, drawn.unit_position, drawn.subtitle) == ("nominal", "suffix", None)


def test_serie_temporal() -> None:
    args = {
        "kind": "line",
        "title": "Saldo",
        "x_type": "temporal",
        "series": [{"name": "Conta", "points": [{"x": "2026-10-01", "y": 10}, {"x": "2026-10-02", "y": 12.5}]}],
    }
    assert build_chart(args).x_type == "temporal"


def test_sem_x_type_o_eixo_e_inferido() -> None:
    """Modelo pequeno omite o `x_type`: datas ISO viram eixo temporal, números viram eixo numérico."""
    datas = [{"x": "2026-07-01", "y": 1200}, {"x": "2026-08-01T10:00", "y": 1850}]
    linha = {"kind": "line", "title": "Saldo", "series": [{"name": "Saldo", "points": datas}]}
    assert build_chart(linha).x_type == "temporal"
    numeros = linha | {"series": [{"name": "s", "points": [{"x": 1, "y": 2}, {"x": 2.5, "y": 3}]}]}
    assert build_chart(numeros).x_type == "quantitative"
    misturado = linha | {"series": [{"name": "s", "points": [{"x": "2026-07-01", "y": 2}, {"x": "jul", "y": 3}]}]}
    assert build_chart(misturado).x_type == "nominal"
    assert build_chart(linha | {"x_type": "nominal"}).x_type == "nominal", "o explícito vence"
    assert build_chart(ROSCA).x_type == "nominal"


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ({"kind": "radar"}, "kind"),
        ({"x_type": "temporal"}, "nominal"),
        ({"series": []}, "séries"),
        ({"series": [{"name": "a", "points": [{"x": "a", "y": -1}]}]}, "negativo"),
        ({"series": ["texto"]}, "objeto"),
        ({"series": [{"name": "a"}]}, "falta o campo"),
    ],
)
def test_erro_volta_legivel_sem_levantar(change: dict[str, Any], fragment: str) -> None:
    result = run(ROSCA | change)
    assert result.charts == () and result.error is not None
    assert result.error.startswith(f"{INVALID}: ") and fragment in result.error


def test_esquema_fecha_os_campos_e_limita_as_series() -> None:
    """O gateway valida os argumentos por este esquema antes do handler (004): campo estranho não chega."""
    assert set(ROSCA) <= set(PARAMETERS["properties"])  # type: ignore[arg-type]
    assert PARAMETERS["additionalProperties"] is False
    assert PARAMETERS["properties"]["series"]["maxItems"] == CHART_MAX_SERIES  # type: ignore[index]


def test_esquema_no_subconjunto_estrito() -> None:
    """Sem `$ref` (o motor achataria o esquema), sem regex e com todo objeto fechado (005 R23)."""

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            assert "$ref" not in node and "pattern" not in node and "allOf" not in node
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(PARAMETERS)


def test_spec_nativa_sem_escrita() -> None:
    spec = chart_spec()
    assert (spec.name, spec.kind, spec.mutates) == ("chart", "native", False)
    assert "gráfico" in spec.description and spec.handler is chart
