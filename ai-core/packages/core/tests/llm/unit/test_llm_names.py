"""Nomes de função na API da OpenAI (ADR-023; T055)."""

from __future__ import annotations

import re

import pytest

from ai_core.llm.domain.names import function_name

PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

pytestmark = pytest.mark.us4


@pytest.mark.parametrize("nome", ["calculate", "consultar_registro", "a-b_c9"])
def test_nome_que_cabe_fica_igual(nome: str) -> None:
    assert function_name(nome) == nome


@pytest.mark.parametrize("nome", ["demo.consultar_registro", "generic.calculate", "x" * 80, "çá.ü", "a b"])
def test_nome_que_nao_cabe_vira_apelido_valido_e_estavel(nome: str) -> None:
    apelido = function_name(nome)
    assert PATTERN.match(apelido), apelido
    assert apelido == function_name(nome)


def test_apelidos_nao_colidem() -> None:
    assert function_name("demo.eco") != function_name("demo_eco")
    assert function_name("demo.eco") != function_name("demo-eco.x")


def test_apelido_comeca_pelo_nome_legivel() -> None:
    assert function_name("demo.consultar_registro").startswith("demo_consultar_registro_")
