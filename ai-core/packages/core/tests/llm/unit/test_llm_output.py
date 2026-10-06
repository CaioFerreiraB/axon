"""T043 — regra pura da restrição de formato do papel `controller` (`domain/output.py`; data-model "Fase 3", R17)."""

from __future__ import annotations

from typing import Any

import pytest

from ai_core.llm.domain.output import CONSTRAINED_ROLES, constraint_problem

pytestmark = pytest.mark.us4

SCHEMA_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {"name": "acao", "schema": {"type": "object", "properties": {"action": {"enum": ["answer"]}}}},
}


def test_so_o_controller_e_restrito() -> None:
    assert frozenset({"controller"}) == CONSTRAINED_ROLES


@pytest.mark.parametrize("role", ["generation", "rerank"])
@pytest.mark.parametrize(
    "formato", [None, {"type": "json_object"}, SCHEMA_FORMAT], ids=["sem", "json_object", "esquema"]
)
def test_papeis_sem_restricao_aceitam_qualquer_formato(role: Any, formato: Any) -> None:
    assert constraint_problem(role, formato) is None


def test_controller_com_esquema_e_aceito() -> None:
    assert constraint_problem("controller", SCHEMA_FORMAT) is None


@pytest.mark.parametrize(
    "formato",
    [
        None,
        {"type": "json_object"},
        {"type": "text"},
        {"type": "json_schema"},
        {"type": "json_schema", "json_schema": {"name": "acao"}},
        {"type": "json_schema", "json_schema": {"name": "acao", "schema": "objeto"}},
        {"type": "json_schema", "json_schema": {"name": "acao", "schema": ["object"]}},
        {"type": "json_schema", "json_schema": "acao"},
    ],
    ids=[
        "sem-formato",
        "json_object",
        "text",
        "json_schema-sem-corpo",
        "json_schema-sem-schema",
        "schema-texto",
        "schema-lista",
        "json_schema-nao-mapeamento",
    ],
)
def test_controller_sem_esquema_e_recusado(formato: Any) -> None:
    motivo = constraint_problem("controller", formato)
    assert motivo is not None
    assert "controller" in motivo
    assert "json_schema" in motivo


def test_o_motivo_nomeia_o_tipo_recebido() -> None:
    motivo = constraint_problem("controller", {"type": "json_object"})
    assert motivo is not None
    assert "json_object" in motivo


def test_a_regra_nao_altera_o_formato() -> None:
    formato: dict[str, Any] = {"type": "json_schema", "json_schema": {"name": "acao", "schema": {"type": "object"}}}
    constraint_problem("controller", formato)
    assert formato == {"type": "json_schema", "json_schema": {"name": "acao", "schema": {"type": "object"}}}
