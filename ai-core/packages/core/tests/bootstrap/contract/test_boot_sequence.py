"""T007 — conformidade da sequência de boot (contracts/boot-sequence.md), com etapas de teste.

Nenhuma plataforma é montada aqui: é o que prova que o executor não conhece módulo nenhum.
"""

from __future__ import annotations

from bootstrap_testkit import Recorder

from ai_core.bootstrap.lifecycle import BootContext, StageStatus, run_stages, shutdown


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
