"""Adapters de arquivo: conjunto dourado em YAML e relatório (linha de base) em JSON (research R16, R20, R23)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ai_core.eval.api import EvalInputError, EvalReport, GoldenSet, GoldenSetError
from ai_core.eval.domain.golden import parse_golden
from ai_core.eval.domain.report import from_data, to_data


class YamlGoldenSetSource:
    def load(self, path: Path) -> GoldenSet:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise GoldenSetError(f"conjunto dourado ilegível: {path}: {error}") from error
        return parse_golden(data)


class JsonReportStore:
    """`BaselineStore` em arquivo: a linha de base é um relatório."""

    def load(self, path: Path) -> EvalReport | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise EvalInputError(f"relatório ilegível: {path}: {error}") from error
        return from_data(data)

    def save(self, path: Path, report: EvalReport) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_data(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
