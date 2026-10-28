"""As citações como fontes do Open WebUI (FR-005b, ADR-051): formato puro."""

from __future__ import annotations

import pytest

from axon_ai.http.domain.sources import source_events, web_url


def test_uma_fonte_por_citacao_na_ordem_do_n_com_id_pelo_chunk() -> None:
    events = source_events(
        [
            {"chunk_id": "a", "document": "Doc A", "url": "https://x.org/a.pdf"},
            {"chunk_id": "b", "document": "Doc A", "url": "https://x.org/a.pdf"},
        ]
    )

    assert [e["type"] for e in events] == ["source", "source"]
    assert [e["data"]["metadata"][0]["source"] for e in events] == ["a", "b"], "mesmo PDF, duas fontes"


def test_legenda_sem_secao_nem_pagina_e_so_o_documento() -> None:
    (event,) = source_events([{"chunk_id": "a", "document": "Doc A"}])

    assert event["data"]["source"] == {"id": "a", "name": "Doc A"}
    assert event["data"]["metadata"] == [{"source": "a", "name": "Doc A"}]
    assert event["data"]["document"] == ["Documento: Doc A"], "nunca vazio: o Open WebUI descarta fonte sem documento"


def test_sem_documento_a_legenda_e_o_chunk() -> None:
    (event,) = source_events([{"chunk_id": "a", "section": "Art. 2", "page": 1}])

    assert event["data"]["source"]["name"] == "a — Art. 2, p. 1"
    assert event["data"]["metadata"][0]["page"] == 0


@pytest.mark.parametrize("page", [0, -1, True, "3", None])
def test_pagina_invalida_e_ignorada(page: object) -> None:
    (event,) = source_events([{"chunk_id": "a", "document": "D", "page": page}])

    assert "page" not in event["data"]["metadata"][0]
    assert event["data"]["source"]["name"] == "D"


def test_citacao_sem_chunk_id_nao_vira_fonte() -> None:
    assert source_events([{"document": "D"}, {"chunk_id": " ", "document": "D"}]) == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://x.org/a.pdf#page=3", "https://x.org/a.pdf#page=3"),
        ("HTTP://x.org/a", "HTTP://x.org/a"),
        ("javascript:alert(1)", None),
        ("<b>oi</b>", None),
        ("https://", None),
        ("http://[::1", None),
        ("", None),
        (None, None),
        (3, None),
    ],
)
def test_so_url_http_com_host(value: object, expected: str | None) -> None:
    assert web_url(value) == expected
