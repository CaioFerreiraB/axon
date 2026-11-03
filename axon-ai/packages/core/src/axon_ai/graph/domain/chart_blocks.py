"""Gráficos que a geração declara em JSON na resposta — puro (ADR-054; research R56).

A geração escreve um bloco ` ```axon-chart ` com um objeto JSON no esquema do `Chart` (contrato 001). O filtro o tira
do texto em streaming — segura só o pedaço do fim que ainda pode abrir um bloco —, e `parse_chart` o transforma no
`Chart`, que valida tudo na construção. O que sai daqui segue o caminho dos gráficos de tool (ADR-052).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from axon_ai_contracts import Chart, ChartPoint, ChartSeries

OPEN: Final = "```axon-chart"
CLOSE: Final = "```"
MAX_BLOCK_CHARTS: Final = 4
"""Gráficos por resposta: um modelo que repete o bloco não enche a conversa."""

CHART_BLOCK_INSTRUCTION: Final = (
    "Quando o usuário pedir um gráfico, inclua na resposta um bloco ```axon-chart com um objeto JSON, por exemplo: "
    '```axon-chart\n{"kind": "donut", "title": "Título", "unit": "R$", "unit_position": "prefix", '
    '"series": [{"name": "Série", "points": [{"x": "Categoria A", "y": 120}, {"x": "Categoria B", "y": 80}]}]}\n```\n'
    "A plataforma tira o bloco do texto e desenha o gráfico interativo para o usuário, com a tabela dos dados. "
    "kind é line, area, bar, stacked_bar, scatter, pie, donut ou waterfall. Em pizza, rosca e waterfall, uma série "
    "só; no waterfall, cada y é a variação da etapa (positiva ou negativa), em ordem, e o total é calculado pela "
    'plataforma — não o inclua. Em série temporal, x é a data ISO (2026-10-28) e x_type é "temporal". Até 8 séries. '
    "Use só números que estão nos resultados das ferramentas ou na conversa. Nunca desenhe gráfico em texto, ASCII "
    "ou com caracteres, e não repita um gráfico que já foi mostrado."
)
"""Texto fixo do core na geração de uma execução com tools (ADR-054, item 4). Sem domínio (princípio I)."""

_OPTIONAL: Final = ("subtitle", "x_label", "y_label", "unit")
_ISO_DATE: Final = re.compile(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")
_NOMINAL_KINDS: Final = frozenset({"pie", "donut", "waterfall"})


def _held(text: str, tag: str) -> int:
    """Quantos caracteres do fim de `text` podem ser o começo de `tag` (nunca a marca inteira)."""
    for size in range(min(len(text), len(tag) - 1), 0, -1):
        if text.endswith(tag[:size]):
            return size
    return 0


class ChartBlockFilter:
    """`feed` devolve o texto que já pode sair e guarda em `blocks` o conteúdo de cada bloco fechado; `finish`, o
    resto. Bloco aberto e nunca fechado conta como fechado no fim: o modelo às vezes termina sem a cerca."""

    def __init__(self) -> None:
        self._pending = ""
        self._inside = False
        self.blocks: list[str] = []

    def feed(self, text: str) -> str:
        self._pending += text
        out: list[str] = []
        while True:
            if self._inside:
                end = self._pending.find(CLOSE)
                if end < 0:
                    return "".join(out)
                self.blocks.append(self._pending[:end])
                self._pending = self._pending[end + len(CLOSE) :]
                self._inside = False
                continue
            start = self._pending.find(OPEN)
            if start < 0:
                cut = len(self._pending) - _held(self._pending, OPEN)
                out.append(self._pending[:cut])
                self._pending = self._pending[cut:]
                return "".join(out)
            out.append(self._pending[:start])
            self._pending = self._pending[start + len(OPEN) :]
            self._inside = True

    def finish(self) -> str:
        if self._inside:
            self.blocks.append(self._pending)
            rest = ""
        else:
            rest = self._pending
        self._pending = ""
        self._inside = False
        return rest


def parse_chart(source: str) -> Chart:
    """O conteúdo de um bloco vira o `Chart`; erro legível em `ValueError` (o motor o registra, sem levantar)."""
    try:
        value = json.loads(source)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON inválido: {error.msg}") from None
    if not isinstance(value, Mapping):
        raise ValueError("o bloco precisa ser um objeto JSON")
    try:
        series = tuple(_series(item) for item in _items(value.get("series"), "series"))
        options: dict[str, Any] = {name: value[name] for name in _OPTIONAL if value.get(name) is not None}
        options["unit_position"] = value.get("unit_position") or "suffix"
        options["x_type"] = value.get("x_type") or _inferred_x_type(value.get("kind"), series)
        return Chart(kind=value.get("kind"), title=value.get("title"), series=series, **options)  # type: ignore[arg-type]
    except (TypeError, ValueError, KeyError) as error:
        raise ValueError(str(error)) from None


def _series(item: Mapping[str, Any]) -> ChartSeries:
    points: list[ChartPoint] = []
    for point in _items(item.get("points"), "points", pairs=True):
        if isinstance(point, Mapping):
            points.append(ChartPoint(x=point.get("x"), y=point.get("y")))  # type: ignore[arg-type]
        else:
            points.append(ChartPoint(x=point[0], y=point[1]))
    return ChartSeries(name=item.get("name"), points=tuple(points))  # type: ignore[arg-type]


def _items(value: object, name: str, *, pairs: bool = False) -> Sequence[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{name} precisa ser uma lista")
    for item in value:
        if isinstance(item, Mapping):
            continue
        if pairs and isinstance(item, list) and len(item) == 2:
            continue
        raise TypeError(f"cada item de {name} precisa ser um objeto" + (" ou um par [x, y]" if pairs else ""))
    return value


def _inferred_x_type(kind: object, series: Sequence[ChartSeries]) -> str:
    """Sem `x_type`: temporal quando todo x é data ISO, numérico quando todo x é número, senão de categorias."""
    xs = [point.x for item in series for point in item.points]
    if kind in _NOMINAL_KINDS or not xs:
        return "nominal"
    if all(isinstance(x, float) for x in xs):
        return "quantitative"
    if all(isinstance(x, str) and _ISO_DATE.fullmatch(x) for x in xs):
        return "temporal"
    return "nominal"
