"""Portas secundárias do harness (research R26). Só a composition root (011) — e os testes — escolhem os adapters."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol

from axon_ai.eval.api import EvalReport, GoldenSet
from axon_ai.eval.domain.judging import Judgement as Judgement


class GoldenSetSource(Protocol):
    def load(self, path: Path) -> GoldenSet:
        """O conjunto dourado do arquivo. `GoldenSetError` para arquivo ilegível ou inutilizável; item com problema
        de formato vem em `GoldenSet.invalid`."""
        ...


class BaselineStore(Protocol):
    def load(self, path: Path) -> EvalReport | None:
        """A linha de base (um relatório), ou `None` se o arquivo não existe. `EvalInputError` se ilegível."""
        ...

    def save(self, path: Path, report: EvalReport) -> None: ...


class Judge(Protocol):
    """Juiz offline (FR-006, ADR-007): nunca no caminho da requisição."""

    @property
    def name(self) -> str:
        """`provider/modelo`, para o relatório."""
        ...

    async def judge(
        self, *, question: str, answer: str, passages: Sequence[str], reference: str | None, request_id: str
    ) -> Judgement:
        """NUNCA levanta: falha do modelo ou resposta malformada vira `Judgement(None, None)`."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...
