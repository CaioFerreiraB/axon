"""O evento `coverage_gate` (toque declarado pela 005 na Fase 5, ADR-017; research R39 da 005; T063).

A decisão do portão de cobertura do `rag_first`: contagens, melhor score, limiar, se cobriu e a rota — nunca texto nem
identificador de trecho. É o que a 105 lê para calibrar o limiar.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from trace_testkit import AT

from axon_ai.observability.adapters.jsonl import JsonlTraceBackend
from axon_ai.observability.adapters.memory import InMemoryTraceBackend
from axon_ai.observability.api import CoverageGate
from axon_ai.observability.domain.records import record_type, to_record

pytestmark = pytest.mark.us3


def gate(**overrides: Any) -> CoverageGate:
    fields: dict[str, Any] = {
        "request_id": "req-1",
        "candidates": 8,
        "passages": 5,
        "best_score": 0.87,
        "threshold": None,
        "covered": True,
        "route": "generate",
    }
    return CoverageGate(**(fields | overrides))


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"threshold": 0.8},
        {"threshold": 0.9, "covered": False, "route": "controller"},
        {"candidates": 0, "passages": 0, "best_score": None, "covered": False, "route": "fallback"},
        {"threshold": 0.0},
        {"threshold": 1.0, "covered": False, "route": "fallback"},
        {"best_score": 3.5},
    ],
)
def test_decisao_vira_registro_coverage_gate_sem_campos_vazios(fields: dict[str, Any]) -> None:
    event = gate(**fields)
    record = to_record(event, AT)
    assert record_type(event) == "coverage_gate"
    esperado = {
        "candidates": 8,
        "passages": 5,
        "best_score": 0.87,
        "threshold": None,
        "covered": True,
        "route": "generate",
    } | fields
    assert dict(record.attributes) == {k: v for k, v in esperado.items() if v is not None}


@pytest.mark.parametrize(
    "fields",
    [
        {"request_id": " "},
        {"candidates": -1},
        {"passages": -1},
        {"candidates": True},
        {"passages": 1.0},
        {"candidates": 3, "passages": 5},
        {"passages": 0, "covered": False, "route": "fallback"},
        {"best_score": None},
        {"best_score": math.nan},
        {"threshold": -0.1},
        {"threshold": 1.1},
        {"threshold": math.nan},
        {"route": "loop"},
        {"covered": False},
        {"route": "controller"},
        {"covered": True, "route": "fallback"},
    ],
)
def test_campos_fora_da_regra_sao_recusados(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        gate(**fields)


@pytest.mark.parametrize("backend", ["memoria", "jsonl"])
def test_os_dois_backends_guardam_o_tipo_coverage_gate(backend: str, tmp_path: Any) -> None:
    store = InMemoryTraceBackend() if backend == "memoria" else JsonlTraceBackend(tmp_path)
    store.export(to_record(gate(threshold=0.9, covered=False, route="controller"), AT))
    (record,) = store.read("req-1")
    assert record.type == "coverage_gate"
    assert dict(record.attributes) == {
        "candidates": 8,
        "passages": 5,
        "best_score": 0.87,
        "threshold": 0.9,
        "covered": False,
        "route": "controller",
    }
