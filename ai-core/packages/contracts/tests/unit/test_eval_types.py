"""Tipos de avaliação do contrato (ADR-027; spec 009 Fase 6, T020): o que uma métrica de domínio lê e implementa."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import pytest

from axon_ai_contracts import (
    AgentPack,
    Citation,
    EvalChunk,
    EvalEvidence,
    EvalItem,
    EvalMetric,
    EvalObservation,
    PackBase,
    PackManifest,
    ProvidesEvalMetrics,
)
from axon_ai_contracts.testing import pack_context

AT = datetime(2026, 10, 7, 15, tzinfo=UTC)


def item(**changes: Any) -> EvalItem:
    fields: dict[str, Any] = {"id": "q001", "question": "Quem pode ser patrono?", "reference_time": AT}
    return EvalItem(**(fields | changes))


def test_evidencia_exige_documento() -> None:
    assert EvalEvidence(document="Regulamento").section is None
    assert EvalEvidence(document="Regulamento", section="Regra 31", chunk_id="doc#r31").chunk_id == "doc#r31"
    with pytest.raises(ValueError, match="document"):
        EvalEvidence(document=" ")


def test_item_congela_e_valida() -> None:
    evidencia = EvalEvidence(document="Regulamento")
    criado = item(expected_documents=[evidencia], expected_citations=[evidencia], extra={"ramo": ["lobinho"]})
    assert criado.expected_documents == (evidencia,) and criado.expected_citations == (evidencia,)
    assert criado.reference_answer is None
    with pytest.raises(TypeError):
        criado.extra["novo"] = 1  # type: ignore[index]
    assert criado.extra["ramo"] == ("lobinho",)


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"id": ""}, "id"),
        ({"question": "  "}, "question"),
        ({"reference_time": datetime(2026, 10, 7)}, "reference_time"),
    ],
)
def test_item_invalido(changes: dict[str, Any], field: str) -> None:
    with pytest.raises(ValueError, match=field):
        item(**changes)


def test_trecho_observado() -> None:
    trecho = EvalChunk(chunk_id="doc#r31", score=0.9, document="Regulamento", status="vigente", page=37)
    assert (trecho.version, trecho.section, trecho.page) == (None, None, 37)
    for changes in ({"page": 0}, {"chunk_id": ""}, {"document": ""}, {"score": float("nan")}):
        with pytest.raises(ValueError):
            EvalChunk(**({"chunk_id": "c", "score": 0.5, "document": "D"} | changes))  # type: ignore[arg-type]


def test_observacao_congela() -> None:
    trecho = EvalChunk(chunk_id="c1", score=0.5, document="D")
    citacao: Citation = {"chunk_id": "c1", "document": "D"}
    observada = EvalObservation(
        answer="Resposta [1].",
        citations=[citacao],
        flags={"ungrounded"},
        retrieved=[trecho],
        reranked=[trecho],
        delivered=[trecho],
        issue_kinds=["CoverageInsufficient"],
    )
    assert observada.citations == (citacao,) and observada.flags == frozenset({"ungrounded"})
    assert observada.retrieved == observada.reranked == observada.delivered == (trecho,)
    assert observada.issue_kinds == ("CoverageInsufficient",)
    assert EvalObservation(answer="").delivered == ()


class Vigentes:
    name = "current_rate"
    better: Literal["higher", "lower"] = "higher"
    deterministic = True

    def measure(self, item: EvalItem, observation: EvalObservation) -> float | None:
        if not observation.delivered:
            return None
        return sum(c.status == "vigente" for c in observation.delivered) / len(observation.delivered)


def test_metrica_e_um_protocolo_estrutural() -> None:
    assert isinstance(Vigentes(), EvalMetric)
    assert Vigentes().measure(item(), EvalObservation(answer="")) is None


class Pack(PackBase):
    name = "p"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        return PackManifest(name="p", version="0.1.0")


def test_pack_base_nao_declara_metricas_e_o_hook_e_opcional() -> None:
    assert tuple(Pack().eval_metrics(pack_context("p"))) == ()
    assert isinstance(Pack(), ProvidesEvalMetrics)

    class SemHook:
        name = "s"
        contract_version = "0.2"

        def manifest(self) -> PackManifest:
            return PackManifest(name="s", version="0.1.0")

        def system_prompt(self, ctx: Any) -> None:
            return None

        async def prepare_context(self, view: Any, ctx: Any) -> dict[str, Any]:
            return {}

        def tools(self, ctx: Any) -> tuple[()]:
            return ()

        def retrievers(self, ctx: Any) -> tuple[()]:
            return ()

        def reranker(self, ctx: Any) -> None:
            return None

        def validators(self, ctx: Any) -> tuple[()]:
            return ()

    assert isinstance(SemHook(), AgentPack), "o AgentPack não ganhou membro: pack sem o hook continua conforme"
    assert not isinstance(SemHook(), ProvidesEvalMetrics)
