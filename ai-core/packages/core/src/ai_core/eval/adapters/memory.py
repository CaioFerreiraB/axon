"""Adapters em memória das portas do harness — testes e composição de exemplo (research R26)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from ai_core.eval.api import EvalReport, GoldenSet, GoldenSetError
from ai_core.eval.ports import Judgement


class InMemoryGoldenSetSource:
    def __init__(self, sets: Mapping[Path, GoldenSet] | None = None) -> None:
        self._sets = dict(sets or {})

    def load(self, path: Path) -> GoldenSet:
        if path not in self._sets:
            raise GoldenSetError(f"conjunto dourado não encontrado: {path}")
        return self._sets[path]


class InMemoryBaselineStore:
    def __init__(self) -> None:
        self.reports: dict[Path, EvalReport] = {}

    def load(self, path: Path) -> EvalReport | None:
        return self.reports.get(path)

    def save(self, path: Path, report: EvalReport) -> None:
        self.reports[path] = report


class ScriptedJudge:
    """Juiz de teste: devolve os julgamentos do roteiro em ordem (o último se repete); guarda as chamadas."""

    def __init__(self, script: Sequence[Judgement], *, name: str = "teste/juiz") -> None:
        self._script = list(script)
        self._name = name
        self.calls: list[dict[str, object]] = []

    @property
    def name(self) -> str:
        return self._name

    async def judge(
        self, *, question: str, answer: str, passages: Sequence[str], reference: str | None, request_id: str
    ) -> Judgement:
        self.calls.append(
            {
                "question": question,
                "answer": answer,
                "passages": list(passages),
                "reference": reference,
                "id": request_id,
            }
        )
        if not self._script:
            return Judgement(faithfulness=None, coverage=None)
        return self._script.pop(0) if len(self._script) > 1 else self._script[0]


class FixedEvalClock:
    """`now` fixo e `monotonic` por roteiro (o último valor se repete): latências determinísticas nos testes."""

    def __init__(self, now: datetime, readings: Sequence[float] = (0.0,)) -> None:
        self._now = now
        self._readings = list(readings)

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._readings.pop(0) if len(self._readings) > 1 else self._readings[0]
