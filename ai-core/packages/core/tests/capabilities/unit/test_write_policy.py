"""T026 — a política de escrita (FR-010; US4 cen. 1)."""

from __future__ import annotations

import pytest

from ai_core.capabilities.api import CatalogTool
from ai_core.capabilities.domain.write_policy import allowed_to_write

pytestmark = pytest.mark.us4


def tool(name: str, *, mutates: bool) -> CatalogTool:
    return CatalogTool(name=name, description="d", parameters={}, kind="native", mutates=mutates)


def test_tool_que_muta_so_com_o_nome_exato_em_write_tools() -> None:
    pagar = tool("alfa.pagar", mutates=True)
    assert allowed_to_write(pagar, frozenset({"alfa.pagar"}))
    assert not allowed_to_write(pagar, frozenset({"pagar"}))
    assert not allowed_to_write(pagar, frozenset({"ALFA.pagar"}))


def test_assistant_publico_nao_tem_nenhuma_escrita() -> None:
    """`write_tools` vazio é sempre o caso de Assistant público (003 FR-012)."""
    assert not allowed_to_write(tool("alfa.pagar", mutates=True), frozenset())


def test_tool_que_nao_muta_nao_depende_de_write_tools() -> None:
    assert allowed_to_write(tool("alfa.ler", mutates=False), frozenset())
