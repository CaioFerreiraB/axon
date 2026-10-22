"""O evento `controller_decision` (toque declarado pela 005, ADR-017): regras de campo e nada de argumento nem saída.

Testes da passada da Fase 3 da 005 (T027): a decisão do controller por iteração, com a mesma regra de privacidade do
`tool_call` — identificadores, contagens e motivos curtos escritos pelo emissor.
"""

from __future__ import annotations

from typing import Any

import pytest
from trace_testkit import AT

from axon_ai.observability.adapters.jsonl import JsonlTraceBackend
from axon_ai.observability.adapters.memory import InMemoryTraceBackend
from axon_ai.observability.api import ControllerDecision
from axon_ai.observability.domain.records import record_type, to_record

pytestmark = pytest.mark.us2


def decision(**overrides: Any) -> ControllerDecision:
    fields: dict[str, Any] = {"request_id": "req-1", "iteration": 1, "action": "answer"}
    return ControllerDecision(**(fields | overrides))


@pytest.mark.parametrize(
    "fields",
    [
        {"action": "tool", "tool": "generic.calculate"},
        {"action": "answer"},
        {"action": "invalid", "reason": "JSON malformado"},
        {"action": "limit", "iteration": 3, "reason": "iterations"},
        {"action": "limit", "iteration": 0, "reason": "context"},
    ],
)
def test_decisao_vira_registro_controller_decision_sem_campos_vazios(fields: dict[str, Any]) -> None:
    event = decision(**fields)
    record = to_record(event, AT)
    assert record_type(event) == "controller_decision"
    assert dict(record.attributes) == {"iteration": 1} | fields


@pytest.mark.parametrize(
    "fields",
    [
        {"request_id": " "},
        {"action": "pensar"},
        {"iteration": -1},
        {"iteration": 0, "action": "answer"},
        {"iteration": 0, "action": "tool", "tool": "a.b"},
        {"action": "tool"},
        {"action": "tool", "tool": " "},
        {"action": "answer", "tool": "a.b"},
        {"action": "invalid"},
        {"action": "invalid", "reason": " "},
        {"action": "invalid", "reason": "x", "tool": "a.b"},
        {"action": "limit"},
        {"action": "limit", "reason": "cansou"},
        {"action": "answer", "reason": "porque sim"},
        {"action": "tool", "tool": "a.b", "reason": "porque sim"},
    ],
)
def test_campos_fora_da_regra_sao_recusados(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        decision(**fields)


def test_iteracao_precisa_ser_inteiro() -> None:
    with pytest.raises(ValueError):
        decision(iteration=True)


@pytest.mark.parametrize("backend", ["memoria", "jsonl"])
def test_os_dois_backends_guardam_o_tipo_controller_decision(backend: str, tmp_path: Any) -> None:
    store = InMemoryTraceBackend() if backend == "memoria" else JsonlTraceBackend(tmp_path)
    store.export(to_record(decision(action="tool", tool="generic.calculate"), AT))
    (record,) = store.read("req-1")
    assert record.type == "controller_decision"
    assert dict(record.attributes) == {"iteration": 1, "action": "tool", "tool": "generic.calculate"}


def test_view_image_leva_os_ids_e_so_ela() -> None:
    """ADR-044, item 8: os ids no lugar do nome da tool; vazio vale (a etapa `image_gate` não escolheu nenhuma)."""
    event = ControllerDecision(request_id="req-1", iteration=1, action="view_image", images=["img-0123456789ab"])
    assert event.images == ("img-0123456789ab",)
    record = to_record(event, AT)
    assert dict(record.attributes) == {"iteration": 1, "action": "view_image", "images": ["img-0123456789ab"]}
    assert ControllerDecision(request_id="req-1", iteration=1, action="view_image", images=()).images == ()
    with pytest.raises(ValueError):
        ControllerDecision(request_id="req-1", iteration=1, action="view_image")
    with pytest.raises(ValueError):
        ControllerDecision(request_id="req-1", iteration=1, action="answer", images=())
