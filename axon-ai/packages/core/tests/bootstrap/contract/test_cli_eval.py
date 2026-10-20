"""`axon eval run|compare` (spec 009 Fase 6, research R25; T041): a CLI no perfil `test`, com o Assistant genérico
— sem recuperação, as métricas de recuperação saem ausentes; o harness com recuperação é provado em tests/eval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest
from bootstrap_testkit import ASSISTANTS_YAML, PACKS_YAML, FakeServer

from axon_ai.bootstrap import cli

pytestmark = pytest.mark.us2

GOLDEN: Final = """
version: 1
name: geral
assistant: geral
items:
  - id: q001
    question: "Qual é a capital do Brasil?"
    reference_time: "2026-10-07T12:00:00-03:00"
    reference_answer: "Brasília."
"""


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("AXON_DEV_API_KEY", "AXON_OIDC_ISSUER", "AXON_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "packs.yaml").write_text(PACKS_YAML, encoding="utf-8")
    (tmp_path / "assistants.yaml").write_text(ASSISTANTS_YAML, encoding="utf-8")
    (tmp_path / "golden.yaml").write_text(GOLDEN, encoding="utf-8")
    monkeypatch.setenv("AXON_PROFILE", "test")
    monkeypatch.setenv("AXON_PACKS_FILE", str(tmp_path / "packs.yaml"))
    monkeypatch.setenv("AXON_ASSISTANTS_FILE", str(tmp_path / "assistants.yaml"))
    return tmp_path


def test_eval_run_grava_o_relatorio(ambiente: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = ambiente / "r.json"
    codigo = cli.main(
        ["eval", "run", "--golden", str(ambiente / "golden.yaml"), "--report", str(report)], server=FakeServer()
    )
    saida = capsys.readouterr()
    assert codigo == 0, saida.err
    assert "conjunto geral · Assistant geral · sem juiz" in saida.out
    dados = json.loads(report.read_text(encoding="utf-8"))
    metricas = {m["name"]: m for m in dados["metrics"]}
    assert metricas["recall@5"]["value"] is None, "o chat não recupera"
    assert metricas["latency_ms_p50"]["value"] is not None and dados["items"][0]["failure"] is None

    codigo = cli.main(["eval", "compare", str(report), str(report)], server=FakeServer())
    assert codigo == 0 and "geral" in capsys.readouterr().out


def test_entradas_invalidas(ambiente: Path, capsys: pytest.CaptureFixture[str]) -> None:
    golden = str(ambiente / "golden.yaml")
    assert cli.main(["eval", "run", "--golden", str(ambiente / "nao.yaml")], server=FakeServer()) == 2
    assert cli.main(["eval", "run", "--golden", golden, "--assistant", "nao-existe"], server=FakeServer()) == 2
    assert cli.main(["eval", "run", "--golden", golden, "--principal", "eval"], server=FakeServer()) == 2
    assert cli.main(["eval", "run", "--golden", golden, "--judge", "sem-barra"], server=FakeServer()) == 2
    assert cli.main(["eval", "compare", str(ambiente / "nao.json")], server=FakeServer()) == 2
    erros = capsys.readouterr().err
    assert "conjunto dourado inválido" in erros and "nao-existe" in erros and "--principal" in erros
