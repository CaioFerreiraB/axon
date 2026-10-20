"""Admissão de execuções (FR-016, FR-017; design.md "Admissão e fila"; research R35): a decisão, pura.

Executar, esperar na fila ou recusar depende só de quantas execuções estão em andamento, de quantos pedidos esperam e
dos limites do operador. As vagas e a fila em si são estado em memória do serviço (`ExecutionSlots`), por processo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Literal

MAX_EXECUTIONS_RANGE: Final = (1, 64)
QUEUE_SIZE_RANGE: Final = (0, 1000)
MAX_WAIT_RANGE: Final = (timedelta(milliseconds=1), timedelta(seconds=600))

type Decision = Literal["run", "queue", "reject"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AdmissionLimits:
    """Limites do operador (011): execuções simultâneas, tamanho da fila (0 = sem fila) e espera máxima nela."""

    max_executions: int
    queue_size: int
    max_wait: timedelta

    def __post_init__(self) -> None:
        _within("max_executions", self.max_executions, MAX_EXECUTIONS_RANGE)
        _within("queue_size", self.queue_size, QUEUE_SIZE_RANGE)
        low, high = MAX_WAIT_RANGE
        if not low <= self.max_wait <= high:
            raise ValueError(f"max_wait precisa estar entre {low} e {high}: {self.max_wait}")


def decide(running: int, queued: int, limits: AdmissionLimits) -> Decision:
    """Vaga livre → executa; vagas cheias e fila com lugar → espera; senão → recusa."""
    if running < limits.max_executions:
        return "run"
    if queued < limits.queue_size:
        return "queue"
    return "reject"


def retry_after(limits: AdmissionLimits) -> int:
    """Segundos para tentar de novo: a espera máxima, arredondada para cima, no mínimo 1."""
    return max(1, math.ceil(limits.max_wait.total_seconds()))


def _within(name: str, value: int, bounds: tuple[int, int]) -> None:
    low, high = bounds
    if not low <= value <= high:
        raise ValueError(f"{name} precisa estar entre {low} e {high}: {value}")
