"""Conversão do conjunto dourado lido do YAML (research R16; T025). Pura: recebe o mapeamento já lido."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from ai_core.eval.api import DEFAULT_K, Evidence, GoldenSetError
from ai_core.eval.domain.golden import parse_golden

pytestmark = pytest.mark.us2


def item(**changes: Any) -> dict[str, Any]:
    return {
        "id": "q001",
        "question": "Quem pode ser patrono?",
        "reference_time": "2026-10-07T12:00:00-03:00",
        "expected_documents": [{"document": "Regulamento", "section": "Regra 31"}],
        **changes,
    }


def golden(*items: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {"version": 1, "name": "g", "items": list(items), **changes}


def test_conjunto_valido_com_defaults() -> None:
    conjunto = parse_golden(golden(item(), item(id="q002", reference_answer="Pessoas inspiradoras.")))
    assert (conjunto.name, conjunto.assistant, conjunto.k, dict(conjunto.tolerances)) == ("g", None, DEFAULT_K, {})
    primeiro = conjunto.items[0]
    assert primeiro.reference_time == datetime(2026, 10, 7, 12, tzinfo=timezone(timedelta(hours=-3)))
    assert primeiro.expected_documents == (Evidence(document="Regulamento", section="Regra 31"),)
    assert conjunto.items[1].reference_answer == "Pessoas inspiradoras."
    assert conjunto.invalid == ()


def test_campos_do_conjunto() -> None:
    conjunto = parse_golden(golden(item(), assistant="docs", k=[3], tolerances={"recall@3": 0.05}))
    assert (conjunto.assistant, conjunto.k, dict(conjunto.tolerances)) == ("docs", (3,), {"recall@3": 0.05})


def test_data_ja_lida_pelo_yaml_e_aceita_se_tiver_fuso() -> None:
    aware = datetime(2026, 10, 7, 15, tzinfo=UTC)
    assert parse_golden(golden(item(reference_time=aware))).items[0].reference_time == aware


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"question": ""}, "question"),
        ({"question": None}, "question"),
        ({"reference_time": "2026-10-07T12:00:00"}, "reference_time"),
        ({"reference_time": "ontem"}, "reference_time"),
        ({"id": "Q 1"}, "id"),
        ({"expected_documents": [{"section": "Regra 31"}]}, "expected_documents"),
        ({"expected_documents": "Regulamento"}, "expected_documents"),
        ({"expected_citations": [{"document": ""}]}, "expected_citations"),
        ({"extra": [1, 2]}, "extra"),
        ({"reference_answer": 3}, "reference_answer"),
    ],
)
def test_item_invalido_nao_derruba_o_conjunto(changes: dict[str, Any], field: str) -> None:
    conjunto = parse_golden(golden(item(**changes), item(id="q002")))
    assert [i.id for i in conjunto.items] == ["q002"]
    (invalido,) = conjunto.invalid
    assert field in invalido.reason


def test_id_repetido_invalida_o_segundo() -> None:
    conjunto = parse_golden(golden(item(), item()))
    assert [i.id for i in conjunto.items] == ["q001"]
    assert conjunto.invalid[0].id == "q001" and "repetido" in conjunto.invalid[0].reason


@pytest.mark.parametrize(
    "data",
    [
        "não é mapeamento",
        {"version": 2, "name": "g", "items": []},
        {"version": 1, "name": "g"},
        {"version": 1, "name": "g", "items": "x"},
        {"version": 1, "items": []},
        {"version": 1, "name": "g", "items": [], "k": [0]},
        {"version": 1, "name": "g", "items": [], "tolerances": {"recall@5": -1}},
        {"version": 1, "name": "g", "items": [], "tolerances": ["x"]},
    ],
)
def test_arquivo_inutilizavel(data: Any) -> None:
    with pytest.raises(GoldenSetError):
        parse_golden(data)
