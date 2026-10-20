"""US4 — comparar modelos com o mesmo harness (contracts/eval-harness.md, verificação 5; research R24; T039)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from bootstrap_testkit import PUBLICO, USER_ASSISTANTS_E_ADMIN, MemoryConfig, write_config
from eval_testkit import PACKS, PRINCIPAL, CitingProvider, Observed, docs_pack, harness
from graph_testkit import ANSWER, ScriptedController

from axon_ai.bootstrap.wiring import platform
from axon_ai.eval.adapters.cli import EXIT_OK, compare_command, run_command
from axon_ai.eval.adapters.files import JsonReportStore, YamlGoldenSetSource
from axon_ai.packs.adapters.memory import InMemoryPackSource

pytestmark = pytest.mark.us4

ASSISTANTS = f"""
assistants:
  docs:{PUBLICO}
    packs: [docs]
    collections: [docs]
    models:
      generation: ollama/qwen3:1.7b
      allow: ["ollama/*"]
  agente:{PUBLICO}
    flow: agentic
    packs: [docs]
    collections: [docs]
    models:
      generation: ollama/qwen3:1.7b
      controller: ctrl/controlador
      allow: ["ollama/*", "ctrl/*"]
{USER_ASSISTANTS_E_ADMIN}"""

GOLDEN = """
version: 1
name: bench
items:
  - id: q001
    question: "Quem pode ser patrono?"
    reference_time: "2026-10-07T12:00:00-03:00"
    expected_documents: [{document: Regulamento}]
"""


async def test_dois_assistants_lado_a_lado_com_anotacoes(tmp_path: Path) -> None:
    golden = tmp_path / "golden.yaml"
    golden.write_text(GOLDEN, encoding="utf-8")
    settings = write_config(tmp_path, packs=PACKS, assistants=ASSISTANTS)
    controller = ScriptedController(["isto não é json", ANSWER])
    plataforma = platform(
        config=MemoryConfig(settings),
        overrides={
            "pack_source": InMemoryPackSource.of(docs_pack(Observed())),
            "providers": {"ollama": CitingProvider(), "ctrl": controller},
        },
    )
    assert plataforma.ok, plataforma.report.render()
    store = JsonReportStore()
    try:
        for assistant, note in (("docs", "RAM 2 GB"), ("agente", "RAM 6 GB")):
            code = await run_command(
                harness(plataforma),
                YamlGoldenSetSource(),
                store,
                golden=golden,
                assistant=assistant,
                principal=PRINCIPAL,
                out=io.StringIO(),
                err=io.StringIO(),
                report=tmp_path / f"{assistant}.json",
                annotations=[note],
            )
            assert code == EXIT_OK
    finally:
        plataforma.aclose()

    out = io.StringIO()
    assert (
        compare_command(store, [tmp_path / "docs.json", tmp_path / "agente.json"], out=out, err=io.StringIO())
        == EXIT_OK
    )
    linhas = {linha.split()[0]: linha.split()[1:] for linha in out.getvalue().splitlines() if linha.strip()}
    assert linhas["métrica"] == ["docs", "agente"]
    assert linhas["controller_invalid_rate"] == ["ausente", "0.5000"]
    for nome in ("ttft_ms_p50", "generation_tokens_per_s", "recall@5"):
        assert len(linhas[nome]) == 2
    assert "docs: RAM 2 GB" in out.getvalue() and "agente: RAM 6 GB" in out.getvalue()


def test_relatorio_ilegivel(tmp_path: Path) -> None:
    err = io.StringIO()
    assert compare_command(JsonReportStore(), [tmp_path / "nao.json"], out=io.StringIO(), err=err) == 2
    assert "não encontrado" in err.getvalue()
