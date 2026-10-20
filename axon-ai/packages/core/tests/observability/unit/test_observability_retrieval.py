"""O evento `retrieval` (toque da Fase 6 da 009, ADR-017; research R15; T022): os trechos candidatos, reordenados e
entregues à geração — identificador, score e proveniência; o texto só dos entregues, cortado e redigido."""

from __future__ import annotations

import math
from typing import Any

import pytest
from trace_testkit import AT

from axon_ai.observability.adapters.jsonl import JsonlTraceBackend
from axon_ai.observability.adapters.memory import InMemoryTraceBackend
from axon_ai.observability.api import Retrieval, RetrievedChunk
from axon_ai.observability.domain.records import record_type, to_record

pytestmark = pytest.mark.us2


def chunk(chunk_id: str = "doc#r31@p37", **changes: Any) -> RetrievedChunk:
    fields: dict[str, Any] = {
        "chunk_id": chunk_id,
        "score": 0.87,
        "document": "Regulamento",
        "version": "2025",
        "status": "vigente",
        "section": "Regra 31",
        "page": 37,
    }
    return RetrievedChunk(**(fields | changes))


@pytest.mark.parametrize(
    "changes", [{"chunk_id": " "}, {"document": ""}, {"page": 0}, {"score": math.nan}, {"score": "0.5"}]
)
def test_trecho_fora_da_regra(changes: dict[str, Any]) -> None:
    with pytest.raises((ValueError, TypeError)):
        chunk(**changes)


def test_trecho_sem_proveniencia_opcional() -> None:
    minimo = RetrievedChunk(chunk_id="c1", score=0.1, document="D")
    assert (minimo.version, minimo.status, minimo.section, minimo.page) == (None, None, None, None)


def test_registro_sem_texto_e_sem_campos_vazios() -> None:
    evento = Retrieval(
        request_id="req-1",
        retrieved=[chunk("a"), RetrievedChunk(chunk_id="b", score=0.2, document="D")],
        reranked=[chunk("a")],
        delivered=[chunk("a")],
    )
    assert evento.retrieved == (chunk("a"), RetrievedChunk(chunk_id="b", score=0.2, document="D"))
    record = to_record(evento, AT)
    assert record_type(evento) == "retrieval"
    attributes = dict(record.attributes)
    assert attributes["retrieved"][1] == {"chunk_id": "b", "score": 0.2, "document": "D"}
    assert attributes["delivered"] == [
        {
            "chunk_id": "a",
            "score": 0.87,
            "document": "Regulamento",
            "version": "2025",
            "status": "vigente",
            "section": "Regra 31",
            "page": 37,
        }
    ]
    assert "text" not in str(attributes)


def test_so_os_entregues_levam_texto_cortado_e_redigido() -> None:
    longo = "regra " * 500 + " token=abc123 fim"
    evento = Retrieval(request_id="req-1", retrieved=[chunk("a")], delivered=[chunk("a", text=longo)])
    entregue = to_record(evento, AT).attributes["delivered"][0]
    assert entregue["text"].startswith("regra regra") and "[truncado:" in entregue["text"]
    assert len(entregue["text"]) < len(longo)
    curto = to_record(Retrieval(request_id="r", delivered=[chunk("a", text="senha: token=abc123")]), AT)
    assert "abc123" not in curto.attributes["delivered"][0]["text"]
    with pytest.raises(ValueError, match="entregues"):
        Retrieval(request_id="r", retrieved=[chunk("a", text="x")])
    with pytest.raises(ValueError, match="entregues"):
        Retrieval(request_id="r", reranked=[chunk("a", text="x")])


def test_request_id_obrigatorio() -> None:
    with pytest.raises(ValueError):
        Retrieval(request_id=" ", retrieved=(), reranked=(), delivered=())


@pytest.mark.parametrize("backend", ["memoria", "jsonl"])
def test_os_dois_backends_guardam_o_tipo_retrieval(backend: str, tmp_path: Any) -> None:
    store = InMemoryTraceBackend() if backend == "memoria" else JsonlTraceBackend(tmp_path)
    store.export(to_record(Retrieval(request_id="req-1", retrieved=[chunk()], reranked=(), delivered=[chunk()]), AT))
    (record,) = store.read("req-1")
    assert record.type == "retrieval"
    assert record.attributes["delivered"][0]["chunk_id"] == "doc#r31@p37"
