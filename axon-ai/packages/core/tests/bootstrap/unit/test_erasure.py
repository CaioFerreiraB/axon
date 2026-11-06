"""T098 — os apagadores da composição (incremento 9.7, US9; FR-032, FR-033; research R58, R59)."""

from __future__ import annotations

from typing import Any

import pytest

from axon_ai.assistants.api import ErasureReport
from axon_ai.bootstrap.erasure import ORDER, erasers
from axon_ai.capabilities.api import AuditErasureReport
from axon_ai.http.api import ConversationErasureReport
from axon_ai.identity.ports import ErasedData
from axon_ai.mcp.api import McpErasureReport
from axon_ai.observability.api import ObservabilityErasureReport

pytestmark = pytest.mark.us9

PSEUDO = "deleted:0123456789abcdef"


class Seam:
    """Um seam simulado: registra os argumentos e devolve o relatório dado (ou levanta)."""

    def __init__(self, report: Any, *, fail: bool = False) -> None:
        self.report = report
        self.fail = fail
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def erase_subject(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.fail:
            raise RuntimeError("banco do módulo fora do ar")
        return self.report


def _seams(**overrides: Seam) -> dict[str, Seam]:
    seams = {
        "assistants": Seam(
            ErasureReport(
                user_assistants=1, api_keys=2, override_entries=1, authored=3, config_references=("escritor", "geral")
            )
        ),
        "mcp": Seam(McpErasureReport(servers=1)),
        "conversations": Seam(ConversationErasureReport(conversations=2, attachments=1)),
        "audit": Seam(AuditErasureReport(audit_records=4)),
        "observability": Seam(ObservabilityErasureReport(prices=1, destination_settings=1)),
    }
    return seams | overrides


def _factories(seams: dict[str, Seam], built: list[str]) -> dict[str, Any]:
    def factory(name: str) -> Any:
        def build() -> Seam:
            built.append(name)
            return seams[name]

        return build

    return {name: factory(name) for name in seams}


def test_a_ordem_e_a_do_adr_059() -> None:
    assert ORDER == ("assistants", "mcp", "conversations", "audit", "observability")
    assert [e.name for e in erasers(_factories(_seams(), []))] == list(ORDER)


async def test_traduz_cada_relatorio_em_contagens_e_avisos() -> None:
    resultados = {
        e.name: await e.erase("user:ana", actor="user:root", pseudonym=PSEUDO)
        for e in erasers(_factories(_seams(), []))
    }

    assert resultados == {
        "assistants": ErasedData(
            counts={"user_assistants": 1, "api_keys": 2, "override_entries": 1, "authored": 3},
            warnings=("referências na configuração (assistants.yaml): escritor, geral",),
        ),
        "mcp": ErasedData(counts={"servers": 1}),
        "conversations": ErasedData(counts={"conversations": 2, "attachments": 1}),
        "audit": ErasedData(counts={"audit_records": 4}),
        "observability": ErasedData(counts={"prices": 1, "destination_settings": 1}),
    }


async def test_sem_referencias_nao_ha_aviso() -> None:
    seams = _seams(assistants=Seam(ErasureReport()))
    (assistants, *_) = erasers(_factories(seams, []))
    assert (await assistants.erase("user:ana", actor="cli", pseudonym=PSEUDO)).warnings == ()


async def test_cada_seam_recebe_so_o_que_aceita() -> None:
    seams = _seams()
    for eraser in erasers(_factories(seams, [])):
        await eraser.erase("user:ana", actor="user:root", pseudonym=PSEUDO)

    chamadas = {name: seam.calls for name, seam in seams.items()}
    assert chamadas == {
        "assistants": [(("user:ana",), {"actor": "user:root", "pseudonym": PSEUDO})],
        "mcp": [(("user:ana",), {})],
        "conversations": [(("user:ana",), {})],
        "audit": [(("user:ana",), {"pseudonym": PSEUDO})],
        "observability": [(("user:ana",), {"pseudonym": PSEUDO})],
    }


async def test_a_fabrica_so_roda_no_primeiro_apagamento() -> None:
    """R59: a 012 nasce na etapa `identity`, antes dos serviços que os apagadores usam."""
    built: list[str] = []
    (_, mcp, *_) = erasers(_factories(_seams(), built))
    assert built == []

    await mcp.erase("user:ana", actor="cli", pseudonym=PSEUDO)
    await mcp.erase("user:bia", actor="cli", pseudonym=PSEUDO)

    assert built == ["mcp"]


async def test_a_falha_do_seam_sobe_sem_ser_engolida() -> None:
    """A 012 marca o módulo como falho e retoma; a 008 responde 503 (achado U1)."""
    seams = _seams(audit=Seam(AuditErasureReport(), fail=True))
    audit = next(e for e in erasers(_factories(seams, [])) if e.name == "audit")
    with pytest.raises(RuntimeError, match="fora do ar"):
        await audit.erase("user:ana", actor="cli", pseudonym=PSEUDO)
