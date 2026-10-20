"""T084 — `rag_first` com o Pack Runtime (002) e o gateway (004) reais (US4; ADR-026; research R46).

Um pack de teste em memória declara retriever, reranker e dois validators — o primeiro aceita só `[[chunk_id]]` que
esteve no `generation_context`, como o `citation_integrity` da 104. A geração vê `· id: <chunk_id>` em cada trecho; o
id cortado pelo teto não está no contexto, e o validator o aponta.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from graph_testkit import REFERENCE_TIME, RecordingTraceSink, provider, rag, request

from ai_core.assistants.api import Limits
from ai_core.capabilities.adapters.memory import InMemoryAuditLog
from ai_core.capabilities.api import GatewayLimits
from ai_core.capabilities.service import CapabilityService
from ai_core.graph.adapters.clock import FixedClock
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.api import FinalEvent, RagSettings
from ai_core.graph.service import ExecutionService
from ai_core.llm.service import ModelRoutingService
from ai_core.mcp.adapters.memory import InMemoryDiscoveryCache, InMemorySecretResolver, InMemoryServerStore
from ai_core.mcp.ports import McpConfig
from ai_core.mcp.service import McpService
from ai_core.observability.api import CoverageGate, ModelCall, ToolCall, ValidationRun
from ai_core.packs.adapters.memory import InMemoryPackConfigSource, InMemoryPackSource
from ai_core.packs.ports import PackSettings
from ai_core.packs.service import PackRuntime
from axon_ai_contracts import (
    Chunk,
    JSONValue,
    NamedRetriever,
    PackBase,
    PackContext,
    PackManifest,
    TurnView,
    ValidationResult,
    ValidatorContext,
)

pytestmark = pytest.mark.us4

CHUNKS = tuple(
    Chunk(chunk_id=f"doc#r{n}", text="regra " * 60, score=0.9 - n * 0.1, document="Regulamento", section=f"Regra {n}")
    for n in range(1, 5)
)
CITATION = re.compile(r"\[\[([^\]]+)\]\]")


class Retriever:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, Mapping[str, JSONValue] | None]] = []

    async def search(
        self, query: str, *, top_k: int | None = None, filters: Mapping[str, JSONValue] | None = None
    ) -> list[Chunk]:
        self.calls.append((query, top_k, filters))
        return list(CHUNKS)


class KeepOrder:
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return list(documents)[:top_k]


class Citations:
    name = "citacoes"

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        delivered = {item.chunk_id for item in view.generation_context}
        cited = CITATION.findall(view.answer or "")
        unknown = [chunk_id for chunk_id in cited if chunk_id not in delivered]
        return ValidationResult(ok=not unknown, issues=tuple(f"citação fora do contexto: {c}" for c in unknown))


class Second:
    name = "segundo"

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        return ValidationResult(ok=True)


RETRIEVER = Retriever()


class DocsPack(PackBase):
    name = "docs"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        return PackManifest(name="docs", version="0.1.0")

    def system_prompt(self, ctx: PackContext) -> str | None:
        return "Cite pelo identificador que aparece depois de `id:`, como [[id]]."

    async def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]:
        return {"retrieval_filters": {"ano": 2026}}

    def retrievers(self, ctx: PackContext) -> Sequence[NamedRetriever]:
        return (
            NamedRetriever(name="search", description="Busca.", collections=frozenset({"docs"}), retriever=RETRIEVER),
        )

    def reranker(self, ctx: PackContext) -> Any:
        return KeepOrder()

    def validators(self, ctx: PackContext) -> Sequence[Any]:
        return (Citations(), Second())


def _platform(llm: Any, trace: RecordingTraceSink) -> tuple[ExecutionService, PackRuntime]:
    packs = PackRuntime(InMemoryPackSource.of(DocsPack), InMemoryPackConfigSource({"docs": PackSettings(enabled=True)}))
    packs.load()
    clock = FixedClock(REFERENCE_TIME, readings=[1.0, 1.2])
    mcp = McpService(
        store=InMemoryServerStore(),
        config=McpConfig(),
        transports={},
        secrets=InMemorySecretResolver(),
        cache=InMemoryDiscoveryCache(clock),
        clock=clock,
    )
    capabilities = CapabilityService(
        pack_tools=packs, mcp=mcp, audit=InMemoryAuditLog(), trace=trace, clock=clock, limits=GatewayLimits()
    )
    engine = ExecutionService(
        flows=langgraph_runtime(),
        hooks=packs,
        routing=ModelRoutingService(providers={"ollama": llm}, trace=trace, clock=clock),
        trace=trace,
        clock=clock,
        capabilities=capabilities,
        rag=RagSettings(candidates=10, passages=3),
    )
    return engine, packs


async def _run(answer: str, *, limits: Limits | None = None) -> tuple[FinalEvent, RecordingTraceSink, Any]:
    trace = RecordingTraceSink()
    llm = provider(deltas=(answer,))
    engine, packs = _platform(llm, trace)
    grant = rag(composition=packs.compose(["docs"]), collections=frozenset({"docs"}), limits=limits or Limits())
    events = [event async for event in engine.run(grant, request())]
    assert isinstance(events[-1], FinalEvent)
    return events[-1], trace, llm


async def test_a_geracao_ve_o_id_e_a_citacao_entregue_passa() -> None:
    final, trace, llm = await _run("Conforme a Regra 1 [[doc#r1]].")
    (tool_message,) = [m for m in llm.calls[0]["messages"] if m["role"] == "tool"]
    for item in CHUNKS[:3]:
        assert f"[Regulamento — {item.section} · id: {item.chunk_id}]" in tool_message["content"]
    assert "doc#r4" not in tool_message["content"]
    assert [(run.validator, run.ok) for run in trace.of_type(ValidationRun)] == [("citacoes", True), ("segundo", True)]
    (call,) = trace.of_type(ToolCall)
    assert (call.tool, call.kind, call.status) == ("docs.search", "retrieval", "ok")
    assert RETRIEVER.calls[-1] == ("qual é a capital?", 10, {"ano": 2026})
    assert [m.role for m in trace.of_type(ModelCall)] == ["generation"]
    (gate,) = trace.of_type(CoverageGate)
    assert (gate.candidates, gate.passages, gate.route) == (4, 3, "generate")
    assert not [issue for issue in final.errors if issue.severity == "error"]


async def test_citacao_de_trecho_cortado_pelo_teto_e_apontada() -> None:
    _final, _trace, sem_teto = await _run("x")
    sent = sem_teto.calls[0]["messages"]
    final, trace, llm = await _run("Conforme [[doc#r3]].", limits=Limits(max_context_tokens=_ceiling_for_two(sent)))
    (tool_message,) = [m for m in llm.calls[0]["messages"] if m["role"] == "tool"]
    assert "id: doc#r2]" in tool_message["content"] and "doc#r3" not in tool_message["content"]
    runs = {run.validator: run for run in trace.of_type(ValidationRun)}
    assert runs["citacoes"].ok is False and "doc#r3" in runs["citacoes"].issues[0]
    assert "ContextTrimmed" in [issue.kind for issue in final.errors]


def _ceiling_for_two(sent: Sequence[Any]) -> int:
    """Teto que comporta os dois primeiros trechos e não o terceiro: as mensagens que a geração recebeu sem teto, com o
    resultado reduzido aos dois primeiros blocos, medidas pela estimativa do motor."""
    from ai_core.graph.domain.budget import estimate_tokens

    tool_index = next(i for i, m in enumerate(sent) if m["role"] == "tool")
    content = sent[tool_index]["content"]
    blocks = content.split("\n\n")
    two = "\n\n".join(blocks[:2])
    if not two.endswith("</tool_result>"):
        two += "\n</tool_result>"
    shorter = [*sent[:tool_index], {**sent[tool_index], "content": two}, *sent[tool_index + 1 :]]
    return estimate_tokens(shorter)
