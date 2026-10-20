"""Casamento de evidência esperada com trechos observados (research R16; clarificação 2; T026)."""

from __future__ import annotations

import pytest

from ai_core.eval.api import Evidence
from ai_core.eval.domain.matching import first_match, matches, normalize
from axon_ai_contracts import EvalChunk

pytestmark = pytest.mark.us2


def chunk(chunk_id: str, document: str = "Regulamento", section: str | None = None) -> EvalChunk:
    return EvalChunk(chunk_id=chunk_id, score=0.5, document=document, section=section)


def test_normalizacao() -> None:
    assert normalize("  Princípios,   Organização  e REGRAS ") == "principios, organizacao e regras"


def test_por_documento_e_secao() -> None:
    assert matches(Evidence(document="regulamento"), chunk("c1", "Regulamento", "Regra 31"))
    assert matches(Evidence(document="Regulamento", section="regra 31"), chunk("c1", section="Regra  31"))
    assert not matches(Evidence(document="Regulamento", section="Regra 32"), chunk("c1", section="Regra 31"))
    assert not matches(Evidence(document="Outro"), chunk("c1"))


def test_identificador_tem_prioridade() -> None:
    evidencia = Evidence(document="Regulamento", chunk_id="c2")
    assert not matches(evidencia, chunk("c1"))
    assert matches(evidencia, chunk("c2", document="Qualquer"))


def test_primeira_posicao() -> None:
    trechos = [chunk("c1", "A"), chunk("c2", "B"), chunk("c3", "C")]
    assert first_match([Evidence(document="C"), Evidence(document="B")], trechos) == 2
    assert first_match([Evidence(document="X")], trechos) is None
    assert first_match([], trechos) is None
