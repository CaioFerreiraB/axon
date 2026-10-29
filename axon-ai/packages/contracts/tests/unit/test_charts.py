"""`Chart` e os gráficos no `ToolResult` (FR-031, FR-032, ADR-052, research R35)."""

from __future__ import annotations

import dataclasses

import pytest

from axon_ai_contracts import (
    CHART_KINDS,
    CHART_MAX_POINTS,
    CHART_MAX_SERIES,
    CHART_X_TYPES,
    Chart,
    ChartPoint,
    ChartSeries,
    ToolResult,
)


def series(name: str = "Gastos", values: dict[str, float] | None = None) -> ChartSeries:
    values = values if values is not None else {"Moradia": 2100, "Mercado": 1250.5}
    return ChartSeries(name=name, points=tuple(ChartPoint(x=x, y=y) for x, y in values.items()))


def donut(**overrides: object) -> Chart:
    fields: dict[str, object] = {"kind": "donut", "title": "Gastos por categoria", "series": (series(),)}
    fields.update(overrides)
    return Chart(**fields)  # type: ignore[arg-type]


def test_closed_lists() -> None:
    assert frozenset({"line", "area", "bar", "stacked_bar", "scatter", "pie", "donut"}) == CHART_KINDS
    assert frozenset({"temporal", "quantitative", "nominal"}) == CHART_X_TYPES
    assert (CHART_MAX_SERIES, CHART_MAX_POINTS) == (8, 500)


def test_id_comes_from_the_content() -> None:
    chart = donut()
    assert chart.id.startswith("chart-")
    assert len(chart.id) == len("chart-") + 12
    assert donut().id == chart.id
    assert donut(title="Outro título").id != chart.id
    assert donut(series=(series(values={"Moradia": 2100, "Mercado": 1250}),)).id != chart.id


def test_integer_and_float_values_are_the_same_chart() -> None:
    inteiro = donut(series=(series(values={"A": 2, "B": 3}),))
    real = donut(series=(series(values={"A": 2.0, "B": 3.0}),))
    assert inteiro.id == real.id
    assert inteiro.series[0].points[0].y == 2.0


def test_id_is_not_an_argument() -> None:
    with pytest.raises(TypeError):
        Chart(kind="donut", title="t", series=(series(),), id="chart-000000000000")  # type: ignore[call-arg]


def test_is_frozen() -> None:
    chart = donut()
    with pytest.raises(dataclasses.FrozenInstanceError):
        chart.title = "outro"  # type: ignore[misc]
    assert isinstance(chart.series, tuple)
    assert isinstance(chart.series[0].points, tuple)


@pytest.mark.parametrize(
    ("field", "value"),
    [("kind", "radar"), ("x_type", "ordinal"), ("unit_position", "middle")],
)
def test_closed_enumerations(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=field):
        donut(**{field: value})


def test_texts_are_cleaned() -> None:
    chart = donut(title="  Gastos\n[out]\x00 de   2026 ", subtitle="", unit="R$")
    assert chart.title == "Gastos out de 2026"
    assert chart.subtitle is None
    assert donut(title="x" * 300).title == "x" * 120
    assert ChartSeries(name="a\tb", points=(ChartPoint(x="c\nd", y=1),)).name == "a b"
    assert ChartPoint(x="c\nd", y=1).x == "c d"


def test_title_and_names_are_required() -> None:
    with pytest.raises(ValueError, match="title"):
        donut(title=" \n ")
    with pytest.raises(ValueError, match="name"):
        ChartSeries(name="", points=(ChartPoint(x="a", y=1),))
    with pytest.raises(TypeError):
        donut(title=None)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "3", None])
def test_values_are_finite_numbers(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ChartPoint(x="a", y=value)  # type: ignore[arg-type]


def test_series_need_points() -> None:
    with pytest.raises(ValueError, match="pontos"):
        ChartSeries(name="vazia", points=())
    with pytest.raises(TypeError):
        ChartSeries(name="s", points=({"x": "a", "y": 1},))  # type: ignore[arg-type]


def test_series_limit_and_distinct_names() -> None:
    nine = tuple(series(name=f"s{i}", values={"a": 1}) for i in range(CHART_MAX_SERIES + 1))
    with pytest.raises(ValueError, match="8 séries"):
        Chart(kind="bar", title="t", series=nine)
    assert len(Chart(kind="bar", title="t", series=nine[:8]).series) == 8
    with pytest.raises(ValueError, match="distintos"):
        Chart(kind="bar", title="t", series=(series(name="a"), series(name="a")))
    with pytest.raises(ValueError, match="séries"):
        Chart(kind="bar", title="t", series=())


def test_points_limit_counts_every_series() -> None:
    def many(name: str, count: int) -> ChartSeries:
        return ChartSeries(name=name, points=tuple(ChartPoint(x=float(i), y=1) for i in range(count)))

    ok = Chart(kind="scatter", title="t", x_type="quantitative", series=(many("a", 250), many("b", 250)))
    assert sum(len(item.points) for item in ok.series) == CHART_MAX_POINTS
    with pytest.raises(ValueError, match="500 pontos"):
        Chart(kind="scatter", title="t", x_type="quantitative", series=(many("a", 250), many("b", 251)))


def test_pie_and_donut_shape() -> None:
    for kind in ("pie", "donut"):
        assert donut(kind=kind).kind == kind
        with pytest.raises(ValueError, match="uma série"):
            donut(kind=kind, series=(series(name="a"), series(name="b")))
        with pytest.raises(ValueError, match="negativo"):
            donut(kind=kind, series=(series(values={"a": 3, "b": -1}),))
        with pytest.raises(ValueError, match="soma positiva"):
            donut(kind=kind, series=(series(values={"a": 0, "b": 0}),))
        with pytest.raises(ValueError, match="nominal"):
            donut(kind=kind, x_type="temporal")


def test_x_matches_its_type() -> None:
    dias = series(values={"2026-10-01": 3, "2026-10-02T14:30": 4})
    assert Chart(kind="line", title="t", x_type="temporal", series=(dias,)).x_type == "temporal"
    with pytest.raises(ValueError, match="ISO"):
        Chart(kind="line", title="t", x_type="temporal", series=(series(values={"out/2026": 1}),))
    with pytest.raises(ValueError, match="número"):
        Chart(kind="line", title="t", x_type="quantitative", series=(series(),))
    numeros = ChartSeries(name="n", points=(ChartPoint(x=1, y=2), ChartPoint(x=2.5, y=3)))
    assert Chart(kind="line", title="t", x_type="quantitative", series=(numeros,)).series[0].points[0].x == 1.0
    with pytest.raises(ValueError, match="texto"):
        Chart(kind="bar", title="t", series=(numeros,))


def test_repeated_x_only_in_scatter() -> None:
    repetido = ChartSeries(name="r", points=(ChartPoint(x=1, y=2), ChartPoint(x=1, y=3)))
    assert Chart(kind="scatter", title="t", x_type="quantitative", series=(repetido,)).kind == "scatter"
    with pytest.raises(ValueError, match="repetido"):
        Chart(kind="line", title="t", x_type="quantitative", series=(repetido,))


def test_tool_result_carries_charts() -> None:
    chart = donut()
    result = ToolResult(content="gráfico criado", charts=[chart])
    assert result.charts == (chart,)
    assert ToolResult(content="x").charts == ()
    with pytest.raises(TypeError):
        ToolResult(content="x", charts=({"kind": "donut"},))  # type: ignore[arg-type]
