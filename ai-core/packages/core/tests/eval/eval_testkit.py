"""Fábricas dos testes do harness (spec 009 Fase 6): um pack de teste com recuperação e métrica de domínio, um
gerador que cita o primeiro `id:` que vir, e a plataforma do perfil `test` com o harness composto."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from bootstrap_testkit import PUBLICO, USER_ASSISTANTS_E_ADMIN, MemoryConfig, write_config

from ai_core.assistants.api import Principal
from ai_core.bootstrap.wiring import Platform, platform
from ai_core.eval.adapters.memory import FixedEvalClock
from ai_core.eval.ports import Judge
from ai_core.eval.service import EvalService
from ai_core.packs.adapters.memory import InMemoryPackSource
from axon_ai_contracts import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    Chunk,
    EvalItem,
    EvalObservation,
    JSONValue,
    NamedRetriever,
    PackBase,
    PackContext,
    PackManifest,
    TurnView,
)

PRINCIPAL = Principal(subject="svc:eval", scheme="api_key")
ID = re.compile(r"id: ([^\]\s]+)\]")

CORPUS: tuple[Chunk, ...] = (
    Chunk(
        chunk_id="reg#r31@p37",
        text="Patrono: pessoa inspiradora falecida.",
        score=0.9,
        document="Regulamento",
        section="Regra 31",
        page=37,
        status="vigente",
    ),
    Chunk(
        chunk_id="man#c2@p14",
        text="O ramo atende de 6,5 a 10 anos.",
        score=0.8,
        document="Manual",
        section="Capítulo 2",
        page=14,
        status="vigente",
    ),
    Chunk(
        chunk_id="reg#r12@p20",
        text="Regra antiga sobre faixas etárias.",
        score=0.7,
        document="Regulamento",
        section="Regra 12",
        page=20,
        status="substituido",
    ),
)


@dataclass
class Observed:
    """O que o pack de teste viu: a data de referência de cada preparação e se o retriever está degradado."""

    reference_times: list[datetime] = field(default_factory=list)
    degraded: bool = False


class Retriever:
    def __init__(self, observed: Observed) -> None:
        self._observed = observed

    async def search(
        self, query: str, *, top_k: int | None = None, filters: Mapping[str, JSONValue] | None = None
    ) -> list[Chunk]:
        ordered = list(reversed(CORPUS))[:1] if self._observed.degraded else list(CORPUS)
        return ordered[: top_k or 20]


class KeepOrder:
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return list(documents)[:top_k]


CITATION = re.compile(r"\[\[([^\]]+)\]\]")


class Citations:
    """Validator de teste, como o `citation_integrity` da 104: `[[id]]` do contexto vira citação `[n]`; sem nenhuma,
    a flag `ungrounded`."""

    name = "citacoes"

    async def validate(self, view: TurnView, ctx: Any) -> Any:
        from axon_ai_contracts import ValidationResult

        delivered = {chunk.chunk_id: chunk for chunk in view.generation_context}
        answer = view.answer or ""
        citations: list[Any] = []
        for chunk_id in CITATION.findall(answer):
            if chunk_id in delivered:
                chunk = delivered[chunk_id]
                citations.append(
                    {
                        "chunk_id": chunk_id,
                        "document": chunk.document,
                        "section": chunk.section,
                        "page": chunk.page,
                        "status": chunk.status,
                    }
                )
                answer = answer.replace(f"[[{chunk_id}]]", f"[{len(citations)}]")
        flags = frozenset() if citations else frozenset({"ungrounded"})
        return ValidationResult(ok=bool(citations), answer=answer, citations=citations, flags=flags)


class CurrentRate:
    """Métrica de domínio de teste (ADR-027): a fração dos trechos entregues com status `vigente`."""

    name = "current_rate"
    better = "higher"
    deterministic = True

    def measure(self, item: EvalItem, observation: EvalObservation) -> float | None:
        if not observation.delivered:
            return None
        return sum(chunk.status == "vigente" for chunk in observation.delivered) / len(observation.delivered)


def docs_pack(observed: Observed) -> type[PackBase]:
    class DocsPack(PackBase):
        name = "docs"
        contract_version = "0.2"

        def manifest(self) -> PackManifest:
            return PackManifest(name="docs", version="0.1.0", preferred_flow="rag_first")

        async def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]:
            observed.reference_times.append(view.reference_time)
            return {}

        def retrievers(self, ctx: PackContext) -> Sequence[NamedRetriever]:
            return (
                NamedRetriever(
                    name="search", description="Busca.", collections=frozenset({"docs"}), retriever=Retriever(observed)
                ),
            )

        def reranker(self, ctx: PackContext) -> Any:
            return KeepOrder()

        def validators(self, ctx: PackContext) -> Sequence[Any]:
            return (Citations(),)

        def eval_metrics(self, ctx: PackContext) -> Sequence[Any]:
            return (CurrentRate(),)

    return DocsPack


class CitingProvider:
    """Geração: cita o primeiro `id:` da mensagem `tool`; sem trecho, responde sem citar."""

    name = "ollama"

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Any = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncIterator[ChatChunk]:
        answer = "Nenhum documento oficial foi encontrado."
        for message in messages:
            found = ID.search(message.get("content") or "") if message["role"] == "tool" else None
            if found:
                answer = f"Conforme [[{found.group(1)}]]."
                break
        if not stream:
            return {"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}

        async def chunks() -> AsyncIterator[ChatChunk]:
            yield {"delta": answer, "usage": {"prompt_tokens": 120, "completion_tokens": 8}}
            yield {"delta": "", "finish_reason": "stop"}

        return chunks()

    async def probe(self, model: str) -> Any:
        return SimpleNamespace(available=True, detail=None)

    async def ready(self) -> Any:
        return SimpleNamespace(available=True, detail=None)

    reports_cost = False


PACKS = "packs:\n  docs:\n    enabled: true\n"
ASSISTANTS = f"""
assistants:
  docs:{PUBLICO}
    packs: [docs]
    collections: [docs]
    models:
      generation: ollama/qwen3:1.7b
      allow: ["ollama/*"]
{USER_ASSISTANTS_E_ADMIN}"""


def eval_platform(tmp_path: Path, observed: Observed) -> Platform:
    settings = write_config(tmp_path, packs=PACKS, assistants=ASSISTANTS)
    plataforma = platform(
        config=MemoryConfig(settings),
        overrides={
            "pack_source": InMemoryPackSource.of(docs_pack(observed)),
            "providers": {"ollama": CitingProvider()},
        },
    )
    assert plataforma.ok, plataforma.report.render()
    return plataforma


def harness(plataforma: Platform, *, judge: Judge | None = None, clock: FixedEvalClock | None = None) -> EvalService:
    assert plataforma.engine and plataforma.trace and plataforma.assistants and plataforma.packs
    return EvalService(
        engine=plataforma.engine,
        trace=plataforma.trace,
        grants=plataforma.assistants,
        pack_metrics=plataforma.packs,
        clock=clock or FixedEvalClock(datetime(2026, 10, 13, 12), readings=[float(n) for n in range(1, 400)]),
        core_version="0.3.0-test",
        judge=judge,
    )
