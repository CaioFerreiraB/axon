"""O relatório como estrutura JSON (formato de seam, `version: 1`; research R23) — puro, ida e volta."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final

from ai_core.eval.api import EvalInputError, EvalReport, InvalidItem, ItemResult, MetricValue

VERSION: Final = 1


def to_data(report: EvalReport) -> dict[str, Any]:
    return {
        "version": VERSION,
        "golden_set": report.golden_set,
        "assistant": report.assistant,
        "judge": report.judge,
        "started_at": report.started_at.isoformat(),
        "core_version": report.core_version,
        "k": list(report.k),
        "metrics": [
            {
                "name": m.name,
                "value": m.value,
                "variance": m.variance,
                "n": m.n,
                "deterministic": m.deterministic,
                "better": m.better,
            }
            for m in report.metrics
        ],
        "items": [
            {
                "id": item.id,
                "metrics": dict(item.metrics),
                "citations": [dict(c) for c in item.citations],
                "flags": list(item.flags),
                "issue_kinds": list(item.issue_kinds),
                "gate_route": item.gate_route,
                "failure": item.failure,
                "warnings": list(item.warnings),
            }
            for item in report.items
        ],
        "invalid": [{"id": item.id, "reason": item.reason} for item in report.invalid],
        "annotations": list(report.annotations),
    }


def from_data(data: object) -> EvalReport:
    if not isinstance(data, Mapping) or data.get("version") != VERSION:
        raise EvalInputError(f"relatório em formato desconhecido (esperado version {VERSION})")
    try:
        return EvalReport(
            golden_set=data["golden_set"],
            assistant=data["assistant"],
            judge=data.get("judge"),
            started_at=datetime.fromisoformat(data["started_at"]),
            core_version=data["core_version"],
            k=tuple(data["k"]),
            metrics=[
                MetricValue(
                    name=m["name"],
                    value=m.get("value"),
                    variance=m.get("variance"),
                    n=m["n"],
                    deterministic=m["deterministic"],
                    better=m.get("better"),
                )
                for m in data["metrics"]
            ],
            items=[
                ItemResult(
                    id=i["id"],
                    metrics=i.get("metrics", {}),
                    citations=i.get("citations", []),
                    flags=i.get("flags", []),
                    issue_kinds=i.get("issue_kinds", []),
                    gate_route=i.get("gate_route"),
                    failure=i.get("failure"),
                    warnings=i.get("warnings", []),
                )
                for i in data.get("items", [])
            ],
            invalid=[InvalidItem(id=i.get("id"), reason=i["reason"]) for i in data.get("invalid", [])],
            annotations=data.get("annotations", []),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvalInputError(f"relatório malformado: {error}") from error
