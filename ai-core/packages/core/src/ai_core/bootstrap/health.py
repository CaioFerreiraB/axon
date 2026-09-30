"""Saúde a partir do relatório de boot: o provedor mínimo da porta `HealthProvider` da 008 (research R23 dela).

A saúde agregada completa — providers de modelo, armazenamentos, registry MCP — é a US5 desta spec, na Fase 2; até lá,
cada etapa do boot é um item: ok se concluiu, não ok se degradou ou falhou.
"""

from __future__ import annotations

from ai_core.bootstrap.lifecycle import BootReport, StageStatus
from ai_core.http.ports import HealthItem, HealthReport


class BootReportHealth:
    """Lê o relatório que o boot termina de montar depois de criar a app — por isso o relatório chega depois."""

    def __init__(self) -> None:
        self.report: BootReport | None = None

    async def health(self) -> HealthReport:
        if self.report is None:
            return HealthReport(items=(HealthItem(name="boot", ok=False, detail="boot em andamento"),))
        return HealthReport(
            items=tuple(
                HealthItem(name=outcome.name, ok=outcome.status is StageStatus.OK, detail=outcome.detail)
                for outcome in self.report.stages
            )
        )
