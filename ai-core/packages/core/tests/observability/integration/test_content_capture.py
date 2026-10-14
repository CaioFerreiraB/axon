"""T068 — a captura de conteúdo ponta a ponta (ADR-034; SC-007): do `TracedModel` da 006 ao destino que aceita
conteúdo, com o JSONL de verdade como primário — que nunca recebe texto de prompt e resposta."""

from __future__ import annotations

from pathlib import Path

import pytest
from trace_testkit import AT

from ai_core.llm.adapters.clock import ScriptedClock
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.api import ModelPolicy, ModelRef
from ai_core.llm.service import ModelRoutingService
from ai_core.observability.adapters.jsonl import JsonlTraceBackend
from ai_core.observability.adapters.memory import FixedClock, RecordingDestination
from ai_core.observability.service import TraceService

pytestmark = pytest.mark.us7

PROMPT = "Minha senha é password=hunter2-segredo; resuma o documento confidencial."


async def _run(tmp_path: Path, *, capture: bool) -> tuple[RecordingDestination, RecordingDestination, str]:
    primary = JsonlTraceBackend(tmp_path)
    usage, langfuse = RecordingDestination("usage"), RecordingDestination("langfuse", accepts_content=True)
    trace = TraceService(
        exporter=primary, reader=primary, clock=FixedClock(AT), destinations=(usage, langfuse), capture=lambda: capture
    )
    provider = ScriptedProvider(name="ollama", content="Resumo: nada a declarar.")
    routing = ModelRoutingService(providers={"ollama": provider}, trace=trace, clock=ScriptedClock([0.0, 0.1]))
    model = routing.for_execution(
        policy=ModelPolicy(roles={"generation": ModelRef.parse("ollama/m")}, allow=("ollama/*",)), request_id="req-1"
    ).for_role("generation")
    await model.complete([{"role": "user", "content": PROMPT}])
    written = "".join(path.read_text(encoding="utf-8") for path in tmp_path.rglob("*") if path.is_file())
    return usage, langfuse, written


async def test_desligada_nenhum_destino_recebe_texto(tmp_path: Path) -> None:
    usage, langfuse, written = await _run(tmp_path, capture=False)
    assert [r.type for r in langfuse.records] == ["model_call"] == [r.type for r in usage.records]
    assert "resuma o documento" not in written and "model_exchange" not in written


async def test_ligada_so_o_langfuse_recebe_redigido_e_o_jsonl_nada(tmp_path: Path) -> None:
    usage, langfuse, written = await _run(tmp_path, capture=True)
    assert [r.type for r in langfuse.records] == ["model_call", "model_exchange"]
    assert [r.type for r in usage.records] == ["model_call"]
    content = str(langfuse.records[1].attributes)
    assert "resuma o documento confidencial" in content and "hunter2-segredo" not in content
    assert "Resumo: nada a declarar." in content
    assert "resuma o documento" not in written and "model_exchange" not in written  # SC-007
