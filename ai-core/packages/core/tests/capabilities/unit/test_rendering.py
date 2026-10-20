"""T016 — conteúdo em texto (contracts/fencing.md, "Renderização"); o id de cada trecho (ADR-026; 005 T060)."""

from __future__ import annotations

import pytest
from capabilities_testkit import chunk
from hypothesis import given
from hypothesis import strategies as st

from ai_core.capabilities.domain.rendering import NO_RESULTS, render_chunks, render_value, render_within
from axon_ai_contracts import Chunk

pytestmark = pytest.mark.us2


def test_texto_como_esta() -> None:
    assert render_value("olá <b>") == "olá <b>"


def test_outros_valores_em_json_com_chaves_ordenadas() -> None:
    assert render_value({"b": 2, "a": "ã"}) == '{"a": "ã", "b": 2}'
    assert render_value([1, (2, 3)]) == "[1, [2, 3]]"
    assert render_value(3.5) == "3.5"


def test_chunks_com_proveniencia_e_identificador() -> None:
    texto = render_chunks([chunk(1), chunk(2, section=None, page=None)])
    assert texto == "[doc-1 — Seção 1, p. 3 · id: c1]\ntrecho 1\n\n[doc-2 · id: c2]\ntrecho 2"


@pytest.mark.parametrize(
    ("section", "page", "reference"),
    [
        ("Regra 33", 9, "[Doc — Regra 33, p. 9 · id: doc#r33@p9]"),
        (None, 9, "[Doc, p. 9 · id: doc#r33@p9]"),
        ("Regra 33", None, "[Doc — Regra 33 · id: doc#r33@p9]"),
        (None, None, "[Doc · id: doc#r33@p9]"),
    ],
)
def test_linha_de_referencia_do_adr_026(section: str | None, page: int | None, reference: str) -> None:
    trecho = Chunk(chunk_id="doc#r33@p9", text="O uniforme…", score=0.9, document="Doc", section=section, page=page)
    assert render_chunks([trecho]) == f"{reference}\nO uniforme…"


def test_o_texto_do_trecho_nao_muda() -> None:
    trecho = chunk(1, text="linha 1\nlinha 2 · id: falso")
    assert render_chunks([trecho]).endswith("\nlinha 1\nlinha 2 · id: falso 1")
    assert trecho.text == "linha 1\nlinha 2 · id: falso 1"


def test_sem_chunks() -> None:
    assert render_chunks([]) == NO_RESULTS == "nenhum resultado"
    vazio = render_within([], max_bytes=1024)
    assert (vazio.text, vazio.chunks, vazio.truncated) == ("nenhum resultado", (), False)


def test_dentro_do_limite_e_igual_a_renderizacao_completa() -> None:
    trechos = [chunk(1), chunk(2), chunk(3)]
    cabe = render_within(trechos, max_bytes=10_000)
    assert cabe.text == render_chunks(trechos)
    assert cabe.chunks == tuple(trechos) and not cabe.truncated


def test_corta_por_trecho_inteiro_e_lista_so_os_que_entraram() -> None:
    trechos = [chunk(n, text="x" * 200) for n in (1, 2, 3, 4)]
    um = len(render_chunks(trechos[:1]).encode())
    cortado = render_within(trechos, max_bytes=2 * um + 120)
    assert [c.chunk_id for c in cortado.chunks] == ["c1", "c2"]
    assert cortado.truncated
    assert "id: c2]" in cortado.text and "id: c3" not in cortado.text and "id: c4" not in cortado.text
    assert "2 trecho(s) omitido(s)" in cortado.text
    assert len(cortado.text.encode()) <= 2 * um + 120


def test_primeiro_trecho_maior_que_o_limite_entra_cortado_com_a_referencia() -> None:
    trechos = [chunk(1, text="ã" * 2000), chunk(2)]
    cortado = render_within(trechos, max_bytes=1024)
    assert cortado.chunks == (trechos[0],)
    assert cortado.truncated
    assert cortado.text.startswith("[doc-1 — Seção 1, p. 3 · id: c1]\n")
    assert "id: c2" not in cortado.text
    assert len(cortado.text.encode()) <= 1024


@given(
    sizes=st.lists(st.integers(min_value=1, max_value=400), min_size=1, max_size=12),
    max_bytes=st.integers(min_value=1024, max_value=6000),
)
def test_propriedade_o_que_esta_em_chunks_aparece_no_texto(sizes: list[int], max_bytes: int) -> None:
    trechos = [chunk(n, text="é" * size) for n, size in enumerate(sizes, start=1)]
    resultado = render_within(trechos, max_bytes=max_bytes)
    assert len(resultado.text.encode()) <= max_bytes
    assert resultado.chunks == tuple(trechos[: len(resultado.chunks)]) and resultado.chunks
    for trecho in trechos:
        assert (f"id: {trecho.chunk_id}]" in resultado.text) == (trecho in resultado.chunks)
    assert resultado.truncated == (len(resultado.chunks) < len(trechos) or render_chunks(trechos) != resultado.text)
