"""T016 — conteúdo em texto (contracts/fencing.md, "Renderização")."""

from __future__ import annotations

import pytest
from capabilities_testkit import chunk

from ai_core.capabilities.domain.rendering import render_chunks, render_value

pytestmark = pytest.mark.us2


def test_texto_como_esta() -> None:
    assert render_value("olá <b>") == "olá <b>"


def test_outros_valores_em_json_com_chaves_ordenadas() -> None:
    assert render_value({"b": 2, "a": "ã"}) == '{"a": "ã", "b": 2}'
    assert render_value([1, (2, 3)]) == "[1, [2, 3]]"
    assert render_value(3.5) == "3.5"


def test_chunks_com_proveniencia() -> None:
    texto = render_chunks([chunk(1), chunk(2, section=None, page=None)])
    assert texto == "[doc-1 — Seção 1, p. 3]\ntrecho 1\n\n[doc-2]\ntrecho 2"


def test_sem_chunks() -> None:
    assert render_chunks([]) == "nenhum resultado"
