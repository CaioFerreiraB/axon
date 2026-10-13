"""US3 — barrar regressões (contracts/eval-harness.md, verificações 3 e 4; research R20; T037)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from eval_testkit import PRINCIPAL, Observed, eval_platform, harness

from ai_core.eval.adapters.cli import EXIT_INVALID, EXIT_OK, EXIT_REGRESSION, run_command
from ai_core.eval.adapters.files import JsonReportStore, YamlGoldenSetSource
from ai_core.eval.adapters.memory import ScriptedJudge
from ai_core.eval.ports import Judgement

pytestmark = pytest.mark.us3

GOLDEN = """
version: 1
name: regressao
assistant: docs
k: [1, 2]
items:
  - id: q001
    question: "Quem pode ser patrono?"
    reference_time: "2026-10-07T12:00:00-03:00"
    expected_documents: [{document: Regulamento, section: Regra 31}]
  - id: q002
    question: "Qual a faixa etária?"
    reference_time: "2026-10-07T12:00:00-03:00"
    expected_documents: [{document: Manual}]
"""


async def rodar(tmp_path: Path, observed: Observed, juiz: ScriptedJudge, **kwargs: object) -> tuple[int, str]:
    golden = tmp_path / "golden.yaml"
    golden.write_text(GOLDEN, encoding="utf-8")
    workdir = tmp_path / f"p{len(list(tmp_path.iterdir()))}"
    workdir.mkdir()
    plataforma = eval_platform(workdir, observed)
    out, err = io.StringIO(), io.StringIO()
    try:
        code = await run_command(
            harness(plataforma, judge=juiz),
            YamlGoldenSetSource(),
            JsonReportStore(),
            golden=golden,
            assistant=None,
            principal=PRINCIPAL,
            out=out,
            err=err,
            **kwargs,  # type: ignore[arg-type]
        )
    finally:
        plataforma.aclose()
    return code, out.getvalue() + err.getvalue()


async def test_regressao_no_retriever_barra_e_mostra_o_delta(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    observed = Observed()
    bom = ScriptedJudge([Judgement(faithfulness=1.0, coverage=None)])
    code, saida = await rodar(tmp_path, observed, bom, baseline=base, update_baseline=True)
    assert code == EXIT_OK and "gravada a desta rodada" in saida and base.exists()

    observed.degraded = True
    ruim = ScriptedJudge([Judgement(faithfulness=0.0, coverage=None), Judgement(faithfulness=1.0, coverage=None)])
    code, saida = await rodar(tmp_path, observed, ruim, baseline=base, update_baseline=True)
    assert code == EXIT_REGRESSION
    linhas = {linha.split()[0]: linha for linha in saida.splitlines() if linha.strip()}
    assert "REGRESSÃO" in linhas["recall@1"] and "-0.5000" in linhas["recall@1"]
    assert "REGRESSÃO" in linhas["mrr"]
    assert "REGRESSÃO" not in linhas["faithfulness"], "o juiz varia e não barra sozinho"
    assert "linha de base mantida" in saida

    code, saida = await rodar(tmp_path, observed, ruim, baseline=base, update_baseline=True, force=True)
    assert code == EXIT_REGRESSION and "linha de base atualizada" in saida
    observed.degraded = True
    code, _ = await rodar(tmp_path, observed, ruim, baseline=base)
    assert code == EXIT_OK, "a base gravada com --force é a degradada"


async def test_entrada_invalida(tmp_path: Path) -> None:
    golden = tmp_path / "golden.yaml"
    golden.write_text("items: [", encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    code = await run_command(
        None,  # type: ignore[arg-type]
        YamlGoldenSetSource(),
        JsonReportStore(),
        golden=golden,
        assistant="docs",
        principal=PRINCIPAL,
        out=out,
        err=err,
    )
    assert code == EXIT_INVALID and "conjunto dourado inválido" in err.getvalue()
