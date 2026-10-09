"""T007 — conformidade da sequência de boot (contracts/boot-sequence.md), com etapas de teste.

Nenhuma plataforma é montada aqui: é o que prova que o executor não conhece módulo nenhum.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from bootstrap_testkit import (
    AGENTIC_ASSISTANTS_YAML,
    MCP_YAML,
    MCP_YAML_COM_CREDENCIAL,
    MCP_YAML_COM_PROBLEMA,
    OIDC,
    MemoryConfig,
    Recorder,
    body,
    write_config,
)
from fastapi.testclient import TestClient

from ai_core.bootstrap.lifecycle import BootContext, StageStatus, run_stages, shutdown
from ai_core.bootstrap.wiring import Platform, platform


def test_as_etapas_rodam_na_ordem_declarada(recorder: Recorder) -> None:
    stages = [recorder.stage("primeira"), recorder.stage("segunda"), recorder.stage("terceira")]
    report, _ = run_stages(stages)

    assert recorder.ran == ["primeira", "segunda", "terceira"]
    assert [o.name for o in report.stages] == ["primeira", "segunda", "terceira"]
    assert all(o.status is StageStatus.OK for o in report.stages)
    assert report.ok


def test_falha_em_etapa_critica_interrompe_o_boot(recorder: Recorder) -> None:
    stages = [
        recorder.stage("primeira"),
        recorder.stage("segunda", fails=RuntimeError("adapter ausente")),
        recorder.stage("terceira"),
    ]
    report, _ = run_stages(stages)

    assert recorder.ran == ["primeira", "segunda"], "a etapa seguinte não pode rodar"
    assert [o.status for o in report.stages] == [StageStatus.OK, StageStatus.FAILED]
    assert not report.ok


def test_falha_em_etapa_degradavel_nao_interrompe(recorder: Recorder) -> None:
    stages = [
        recorder.stage("primeira"),
        recorder.stage("packs", critical=False, fails=RuntimeError("pack quebrado")),
        recorder.stage("terceira"),
    ]
    report, _ = run_stages(stages)

    assert recorder.ran == ["primeira", "packs", "terceira"]
    assert report.ok
    assert report.degraded == ("packs",)


def test_o_relatorio_nomeia_a_etapa_e_o_motivo(recorder: Recorder) -> None:
    """SC-005: o operador descobre o que falhou sem abrir log."""
    report, _ = run_stages([recorder.stage("adapters", fails=RuntimeError("porta sem adapter"))])

    falha = report.failure()
    assert falha is not None
    assert falha.name == "adapters"
    assert "porta sem adapter" in (falha.detail or "")
    assert "adapters" in report.render()
    assert "porta sem adapter" in report.render()


def test_etapa_que_conclui_degradada_aparece_com_o_motivo(recorder: Recorder) -> None:
    report, _ = run_stages([recorder.degrading_stage("packs", "pack 'x': contrato incompatível")])

    assert report.ok
    assert report.degraded == ("packs",)
    assert "contrato incompatível" in report.render()


def test_encerramento_libera_recursos_na_ordem_inversa(recorder: Recorder) -> None:
    _, context = run_stages([recorder.stage("a"), recorder.stage("b"), recorder.stage("c")])
    shutdown(context)

    assert recorder.closed == ["c", "b", "a"]


def test_falha_critica_desfaz_o_que_ja_foi_construido(recorder: Recorder) -> None:
    stages = [recorder.stage("a"), recorder.stage("b"), recorder.stage("c", fails=RuntimeError("caiu"))]
    run_stages(stages)

    assert recorder.closed == ["c", "b", "a"], "as etapas concluídas são desfeitas na ordem inversa"


def test_falha_ao_liberar_nao_impede_as_demais() -> None:
    liberados: list[str] = []
    context = BootContext()
    context.on_close(lambda: liberados.append("primeiro"))
    context.on_close(_explode)
    context.on_close(lambda: liberados.append("terceiro"))

    shutdown(context)

    assert liberados == ["terceiro", "primeiro"]


def _explode() -> None:
    raise OSError("recurso já fechado")


def test_acrescentar_etapa_nao_muda_o_executor(recorder: Recorder) -> None:
    """É o que permite a 007 e a 003 entrarem nas fases delas sem tocar nesta sequência."""
    base = [recorder.stage("configuration"), recorder.stage("adapters")]
    com_nova = [*base, recorder.stage("mcp_registry"), recorder.stage("engine")]

    report, _ = run_stages(com_nova)

    assert [o.name for o in report.stages] == ["configuration", "adapters", "mcp_registry", "engine"]
    assert report.ok


# --- Fase 3 (T039; contracts/boot-sequence.md, itens 13 a 19): a plataforma real -------------------------------------


def _boot(tmp_path: Path, **kwargs: Any) -> Platform:
    return platform(config=MemoryConfig(write_config(tmp_path, **kwargs)))


@pytest.mark.us1
def test_13_mcp_registry_entre_packs_e_engine(tmp_path: Path) -> None:
    plataforma = _boot(tmp_path, assistants=AGENTIC_ASSISTANTS_YAML, mcp=MCP_YAML)
    assert plataforma.ok, plataforma.report.render()
    assert [o.name for o in plataforma.report.stages] == [
        "configuration",
        "adapters",
        "packs",
        "mcp_registry",
        "engine",
        "assistants",
        "api",
    ]
    assert plataforma.mcp is not None and plataforma.capabilities is not None


@pytest.mark.us1
def test_14_entrada_com_problema_degrada_mcp_registry_e_o_boot_conclui(tmp_path: Path) -> None:
    plataforma = _boot(tmp_path, mcp=MCP_YAML_COM_PROBLEMA)
    assert plataforma.ok
    (etapa,) = [o for o in plataforma.report.stages if o.name == "mcp_registry"]
    assert etapa.status is StageStatus.DEGRADED
    assert "sem_politica" in (etapa.detail or "")


@pytest.mark.us1
def test_15_arquivo_malformado_para_o_boot_na_configuracao(tmp_path: Path) -> None:
    plataforma = _boot(tmp_path, mcp="servers: [isso, nao, e, mapa\n")
    assert not plataforma.ok
    failure = plataforma.report.failure()
    assert failure is not None and failure.name == "configuration"
    assert "mcp.yaml" in (failure.detail or "")


@pytest.mark.us1
@pytest.mark.parametrize("profile", ["memory", "test"])
def test_16_agentic_e_oferecido_nos_perfis(tmp_path: Path, profile: str) -> None:
    plataforma = _boot(tmp_path, profile=profile)
    assert plataforma.engine is not None
    assert plataforma.engine.flows() == frozenset({"chat", "agentic", "rag_first"})
    assert plataforma.engine.flow_roles()["rag_first"] == ("generation",)
    plataforma.aclose()


@pytest.mark.us3
def test_16b_os_numeros_do_rag_first_chegam_ao_motor(tmp_path: Path) -> None:
    """005 T087: `AI_CORE_RAG_*` → `RagSettings` do motor; valor inválido para o boot nomeando a variável."""
    from ai_core.bootstrap.settings import ConfigurationError, EnvConfigSource

    settings = EnvConfigSource(
        {"AI_CORE_RAG_CANDIDATES": "12", "AI_CORE_RAG_PASSAGES": "4", "AI_CORE_RAG_MIN_SCORE": "0.86"}
    ).load()
    from ai_core.bootstrap.wiring import _rag

    rag = _rag(settings)
    assert (rag.candidates, rag.passages, rag.min_score) == (12, 4, 0.86)
    with pytest.raises(ConfigurationError, match="AI_CORE_RAG_PASSAGES"):
        EnvConfigSource({"AI_CORE_RAG_PASSAGES": "0"}).load()


@pytest.mark.us1
def test_17_o_sdk_de_mcp_nunca_registra_em_debug(tmp_path: Path) -> None:
    root = logging.getLogger()
    before = root.level
    root.setLevel(logging.DEBUG)
    try:
        _boot(tmp_path)
        assert logging.getLogger("mcp.client.streamable_http").getEffectiveLevel() == logging.INFO
    finally:
        root.setLevel(before)


@pytest.mark.us1
def test_18_a_003_valida_contra_o_registry_real(tmp_path: Path) -> None:
    plataforma = _boot(tmp_path, assistants=AGENTIC_ASSISTANTS_YAML, mcp=MCP_YAML)
    (etapa,) = [o for o in plataforma.report.stages if o.name == "assistants"]
    assert "perdido" in (etapa.detail or "")
    assert "pesquisador" not in (etapa.detail or "")


@pytest.mark.us1
def test_19_credencial_ausente_degrada_sem_vazar_segredo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CORE_MCP_SECRET_OUTRA", "segredo-outra")
    plataforma = _boot(tmp_path, mcp=MCP_YAML_COM_CREDENCIAL)
    (etapa,) = [o for o in plataforma.report.stages if o.name == "mcp_registry"]
    assert etapa.status is StageStatus.DEGRADED
    assert "cofre" in (etapa.detail or "") and "falta" in (etapa.detail or "")
    assert "segredo-outra" not in plataforma.report.render()


@pytest.mark.us8
def test_agentic_sem_controller_fica_indisponivel_no_boot_e_responde_424(tmp_path: Path) -> None:
    """003 Fase 3 (ADR-019): o motor publica os papéis por flow, a 011 os injeta, e a 003 recusa antes de servir — a
    requisição recebe 424 com o motivo, não mais o 400 que o motor dava na chamada."""
    sem_controller = AGENTIC_ASSISTANTS_YAML.replace(
        "    mcp: [demo]\n    models:\n      generation: ollama/qwen3:1.7b\n      controller: ollama/qwen3:1.7b\n",
        "    models:\n      generation: ollama/qwen3:1.7b\n",
        1,
    )
    plataforma = _boot(tmp_path, assistants=sem_controller)
    (etapa,) = [o for o in plataforma.report.stages if o.name == "assistants"]
    assert "pesquisador" in (etapa.detail or "") and "controller" in (etapa.detail or "")
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="pesquisador"))
    assert response.status_code == 424
    assert "controller" in response.text
