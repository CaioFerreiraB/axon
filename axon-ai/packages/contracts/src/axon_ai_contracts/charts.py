"""Gráficos: os dados que uma tool devolve para a plataforma desenhar (FR-031, ADR-052, research R35).

O contrato carrega dados, nunca HTML nem especificação de biblioteca: quem desenha é a API, a partir deste esquema
fechado. Tudo é validado na construção, e o `id` vem do conteúdo, como o do `Attachment`.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from axon_ai_contracts._freeze import freeze_sequence

type ChartKind = Literal["line", "area", "bar", "stacked_bar", "scatter", "pie", "donut"]
type ChartXType = Literal["temporal", "quantitative", "nominal"]
type UnitPosition = Literal["prefix", "suffix"]

CHART_KINDS: frozenset[str] = frozenset({"line", "area", "bar", "stacked_bar", "scatter", "pie", "donut"})
CHART_X_TYPES: frozenset[str] = frozenset({"temporal", "quantitative", "nominal"})
CHART_MAX_SERIES = 8
"""As oito cores de série validadas (ADR-052, item 1): uma nona seria gerada, não validada."""
CHART_MAX_POINTS = 500
"""Teto de pontos somando todas as séries: os dados passam pelos argumentos do controller."""

_UNIT_POSITIONS = frozenset({"prefix", "suffix"})
_ROUND_KINDS = frozenset({"pie", "donut"})
_TITLE_MAX_CHARS = 120
_LABEL_MAX_CHARS = 60
_UNIT_MAX_CHARS = 12
_REMOVED = re.compile(r"[\[\]\x00-\x1f\x7f]")
_SPACES = re.compile(r"\s+")


def _clean(name: str, value: object, max_chars: int, *, optional: bool) -> str | None:
    """Texto vindo de fora: sem quebras de linha, controles nem `[`/`]` (que fechariam a marca do gráfico), cortado."""
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} precisa ser str, recebido {type(value).__name__}")
    text = _SPACES.sub(" ", _REMOVED.sub(" ", value)).strip()[:max_chars].strip()
    if not text and not optional:
        raise ValueError(f"{name} não pode ser vazio")
    return text or None


def _number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} precisa ser número, recebido {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} precisa ser finito, recebido {value!r}")
    return number


def _iso(value: str) -> bool:
    """Data (`2026-10-28`) ou data e hora ISO (`2026-10-28T14:00`)."""
    parse = datetime.fromisoformat if "T" in value or " " in value else date.fromisoformat
    try:
        parse(value)
    except ValueError:
        return False
    return True


@dataclass(frozen=True, slots=True, kw_only=True)
class ChartPoint:
    """Um ponto: `x` é texto (categoria ou data ISO) ou número; `y` é sempre número finito."""

    x: str | float
    y: float

    def __post_init__(self) -> None:
        if isinstance(self.x, str):
            object.__setattr__(self, "x", _clean("x", self.x, _LABEL_MAX_CHARS, optional=False))
        else:
            object.__setattr__(self, "x", _number("x", self.x))
        object.__setattr__(self, "y", _number("y", self.y))


@dataclass(frozen=True, slots=True, kw_only=True)
class ChartSeries:
    """Uma série nomeada; a cor dela é a da posição no `Chart`, nunca a da grandeza."""

    name: str
    points: tuple[ChartPoint, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _clean("name", self.name, _LABEL_MAX_CHARS, optional=False))
        points = freeze_sequence(self.points)
        for item in points:
            if not isinstance(item, ChartPoint):
                raise TypeError(f"points só aceita ChartPoint, recebido {type(item).__name__}")
        if not points:
            raise ValueError(f"a série {self.name!r} não tem pontos")
        object.__setattr__(self, "points", points)


@dataclass(frozen=True, slots=True, kw_only=True)
class Chart:
    """Gráfico que acompanha um resultado de tool (ADR-052).

    O `id` vem do conteúdo — `chart-` mais os 12 primeiros hexadecimais do SHA-256 da forma canônica —, então o mesmo
    gráfico tem o mesmo id em qualquer lugar. Os textos são dado não confiável e saem limpos da construção; quem os
    põe em HTML ou markdown ainda escapa.
    """

    kind: ChartKind
    title: str
    series: tuple[ChartSeries, ...]
    x_type: ChartXType = "nominal"
    subtitle: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    unit: str | None = None
    unit_position: UnitPosition = "suffix"
    id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.kind not in CHART_KINDS:
            raise ValueError(f"kind inválido: {self.kind!r} (esperado {sorted(CHART_KINDS)})")
        if self.x_type not in CHART_X_TYPES:
            raise ValueError(f"x_type inválido: {self.x_type!r} (esperado {sorted(CHART_X_TYPES)})")
        if self.unit_position not in _UNIT_POSITIONS:
            raise ValueError(f"unit_position inválido: {self.unit_position!r} (esperado prefix ou suffix)")
        object.__setattr__(self, "title", _clean("title", self.title, _TITLE_MAX_CHARS, optional=False))
        for name in ("subtitle", "x_label", "y_label"):
            object.__setattr__(self, name, _clean(name, getattr(self, name), _TITLE_MAX_CHARS, optional=True))
        object.__setattr__(self, "unit", _clean("unit", self.unit, _UNIT_MAX_CHARS, optional=True))
        series = freeze_sequence(self.series)
        for item in series:
            if not isinstance(item, ChartSeries):
                raise TypeError(f"series só aceita ChartSeries, recebido {type(item).__name__}")
        object.__setattr__(self, "series", series)
        self._check_shape()
        object.__setattr__(self, "id", "chart-" + hashlib.sha256(self._canonical()).hexdigest()[:12])

    def _check_shape(self) -> None:
        if not self.series:
            raise ValueError("o gráfico não tem séries")
        if len(self.series) > CHART_MAX_SERIES:
            raise ValueError(f"no máximo {CHART_MAX_SERIES} séries, recebidas {len(self.series)}")
        names = [item.name for item in self.series]
        if len(set(names)) != len(names):
            raise ValueError("os nomes das séries precisam ser distintos")
        total = sum(len(item.points) for item in self.series)
        if total > CHART_MAX_POINTS:
            raise ValueError(f"no máximo {CHART_MAX_POINTS} pontos somando as séries, recebidos {total}")
        if self.kind in _ROUND_KINDS:
            self._check_round()
        for item in self.series:
            self._check_x(item)

    def _check_round(self) -> None:
        if len(self.series) != 1:
            raise ValueError(f"{self.kind} tem uma série só, recebidas {len(self.series)}")
        if self.x_type != "nominal":
            raise ValueError(f"{self.kind} tem x nominal (as fatias), recebido {self.x_type!r}")
        values = [point.y for point in self.series[0].points]
        if any(value < 0 for value in values):
            raise ValueError(f"{self.kind} não aceita valor negativo")
        if sum(values) <= 0:
            raise ValueError(f"{self.kind} precisa de soma positiva")

    def _check_x(self, series: ChartSeries) -> None:
        xs = [point.x for point in series.points]
        if self.x_type == "quantitative":
            if not all(isinstance(x, float) for x in xs):
                raise ValueError(f"x quantitativo precisa ser número (série {series.name!r})")
        elif self.x_type == "temporal":
            if not all(isinstance(x, str) and _iso(x) for x in xs):
                raise ValueError(f"x temporal precisa ser data ISO, como 2026-10-28 (série {series.name!r})")
        elif not all(isinstance(x, str) for x in xs):
            raise ValueError(f"x nominal precisa ser texto (série {series.name!r})")
        if self.kind != "scatter" and len(set(xs)) != len(xs):
            raise ValueError(f"x repetido na série {series.name!r}")

    def _canonical(self) -> bytes:
        body = {
            "kind": self.kind,
            "title": self.title,
            "subtitle": self.subtitle,
            "x_type": self.x_type,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "unit": self.unit,
            "unit_position": self.unit_position,
            "series": [
                {"name": item.name, "points": [[point.x, point.y] for point in item.points]} for item in self.series
            ],
        }
        return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
