"""T011 e T017 — conferência de esquema e validação de argumentos (research R5; FR-006)."""

from __future__ import annotations

import time

import pytest
from capabilities_testkit import TEXT_SCHEMA

from ai_core.capabilities.domain.arguments import check_schema, validate_arguments
from ai_core_contracts import RETRIEVAL_TOOL_PARAMETERS


@pytest.mark.us1
def test_esquemas_validos_passam() -> None:
    assert check_schema(TEXT_SCHEMA) is None
    assert check_schema(RETRIEVAL_TOOL_PARAMETERS) is None


@pytest.mark.us1
@pytest.mark.parametrize("schema", [{"type": 3}, {"properties": []}, {"required": "texto"}])
def test_esquema_invalido_tem_motivo(schema: dict[str, object]) -> None:
    problem = check_schema(schema)  # type: ignore[arg-type]
    assert problem is not None and problem.strip()


@pytest.mark.us2
def test_argumentos_validos_passam() -> None:
    assert validate_arguments(TEXT_SCHEMA, {"texto": "oi"}, trusted=True) is None


@pytest.mark.us2
@pytest.mark.parametrize(
    ("arguments", "trecho"),
    [({}, "texto"), ({"texto": 3}, "texto"), ({"texto": "oi", "extra": 1}, "extra")],
)
def test_argumentos_fora_do_esquema_nomeiam_o_caminho(arguments: dict[str, object], trecho: str) -> None:
    problem = validate_arguments(TEXT_SCHEMA, arguments, trusted=True)  # type: ignore[arg-type]
    assert problem is not None and trecho in problem


@pytest.mark.us2
def test_argumentos_congelados_validam_como_dicionarios() -> None:
    from types import MappingProxyType

    schema = MappingProxyType(
        {"type": "object", "properties": {"lista": {"type": "array", "items": {"type": "string"}}}}
    )
    assert validate_arguments(schema, MappingProxyType({"lista": ("a", "b")}), trusted=True) is None


CATASTROFICO = {
    "type": "object",
    "properties": {"x": {"type": "string", "pattern": "^(a+)+$"}},
    "required": ["x"],
}


@pytest.mark.us2
def test_mcp_ignora_pattern_de_terceiro_e_aplica_o_resto() -> None:
    """ReDoS: regex de um servidor externo sobre texto do modelo; nenhum prazo assíncrono interrompe CPU (R5)."""
    malicioso = {"x": "a" * 40 + "!"}
    inicio = time.monotonic()
    assert validate_arguments(CATASTROFICO, malicioso, trusted=False) is None
    assert time.monotonic() - inicio < 0.5
    assert validate_arguments(CATASTROFICO, {"x": 3}, trusted=False) is not None, "o tipo continua valendo"
    assert validate_arguments(CATASTROFICO, {}, trusted=False) is not None, "required continua valendo"


@pytest.mark.us2
def test_pattern_vale_para_tool_de_pack() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "string", "pattern": "^a+$"}}}
    assert validate_arguments(schema, {"x": "b"}, trusted=True) is not None


@pytest.mark.us2
def test_ref_remoto_nao_e_buscado() -> None:
    schema = {"$ref": "https://exemplo.invalid/esquema.json"}
    assert validate_arguments(schema, {"x": 1}, trusted=False) is not None
