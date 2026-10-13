"""T059 — decisão de admissão e `Retry-After` (FR-016, FR-017; research R35; contracts/admission.md), puras."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ai_core.http.domain.admission import AdmissionLimits, decide, retry_after

pytestmark = pytest.mark.us6

LIMITS = AdmissionLimits(max_executions=2, queue_size=3, max_wait=timedelta(seconds=60))


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"max_executions": 0}, "max_executions"),
        ({"max_executions": 65}, "max_executions"),
        ({"queue_size": -1}, "queue_size"),
        ({"queue_size": 1001}, "queue_size"),
        ({"max_wait": timedelta(0)}, "max_wait"),
        ({"max_wait": timedelta(seconds=601)}, "max_wait"),
    ],
)
def test_faixas(changes: dict[str, object], field: str) -> None:
    values: dict[str, object] = {"max_executions": 2, "queue_size": 3, "max_wait": timedelta(seconds=60)} | changes
    with pytest.raises(ValueError, match=field):
        AdmissionLimits(**values)  # type: ignore[arg-type]


def test_extremos_validos() -> None:
    AdmissionLimits(max_executions=64, queue_size=0, max_wait=timedelta(milliseconds=1))
    AdmissionLimits(max_executions=1, queue_size=1000, max_wait=timedelta(seconds=600))


@pytest.mark.parametrize(
    ("running", "queued", "decision"),
    [(0, 0, "run"), (1, 0, "run"), (2, 0, "queue"), (2, 2, "queue"), (2, 3, "reject"), (5, 9, "reject")],
)
def test_decide(running: int, queued: int, decision: str) -> None:
    assert decide(running, queued, LIMITS) == decision


def test_sem_fila_vagas_cheias_recusa() -> None:
    limits = AdmissionLimits(max_executions=1, queue_size=0, max_wait=timedelta(seconds=1))
    assert decide(0, 0, limits) == "run"
    assert decide(1, 0, limits) == "reject"


@pytest.mark.parametrize(
    ("wait", "seconds"),
    [
        (timedelta(seconds=60), 60),
        (timedelta(milliseconds=200), 1),
        (timedelta(milliseconds=1500), 2),
        (timedelta(milliseconds=1), 1),
    ],
)
def test_retry_after(wait: timedelta, seconds: int) -> None:
    limits = AdmissionLimits(max_executions=1, queue_size=1, max_wait=wait)
    assert retry_after(limits) == seconds
