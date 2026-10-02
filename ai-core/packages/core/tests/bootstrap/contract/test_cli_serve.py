"""T011b — o comando `ai-core serve` (contracts/boot-sequence.md).

O servidor entra por parâmetro, então o comando é exercitado inteiro sem abrir porta.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from bootstrap_testkit import ASSISTANTS_YAML, ASSISTANTS_YAML_QUEBRADO, PACKS_YAML, FakeServer

from ai_core.bootstrap import cli
from ai_core.bootstrap.profiles import NO_CREDENTIALS_WARNING


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "packs.yaml").write_text(PACKS_YAML, encoding="utf-8")
    (tmp_path / "assistants.yaml").write_text(ASSISTANTS_YAML, encoding="utf-8")
    monkeypatch.setenv("AI_CORE_PROFILE", "test")
    monkeypatch.setenv("AI_CORE_PACKS_FILE", str(tmp_path / "packs.yaml"))
    monkeypatch.setenv("AI_CORE_ASSISTANTS_FILE", str(tmp_path / "assistants.yaml"))
    monkeypatch.setenv("AI_CORE_HOST", "0.0.0.0")
    monkeypatch.setenv("AI_CORE_PORT", "9123")
    return tmp_path


def test_serve_monta_a_plataforma_e_entrega_ao_servidor(
    ambiente: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = cli.main(["serve"], server=server)

    assert codigo == 0
    assert len(server.calls) == 1
    app, host, port, grace = server.calls[0]
    assert app is not None
    assert (host, port) == ("0.0.0.0", 9123)
    assert grace == 10.0


def test_serve_imprime_o_relatorio_de_boot(
    ambiente: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["serve"], server=server)

    saida = capsys.readouterr().out
    for etapa in ("configuration", "adapters", "packs", "engine", "assistants", "api"):
        assert etapa in saida
    assert "9123" in saida


def test_serve_avisa_quando_o_memory_nao_tem_chave_nem_oidc(
    ambiente: Path, monkeypatch: pytest.MonkeyPatch, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    """Falha fechada por falta de configuração: o boot conclui, mas toda credencial será recusada — e isso é dito alto
    (spec, Edge Cases). O `memory` usa o Ollama, mas construir o provider não conecta."""
    monkeypatch.setenv("AI_CORE_PROFILE", "memory")
    for name in ("AI_CORE_DEV_API_KEY", "AI_CORE_OIDC_ISSUER", "AI_CORE_OIDC_AUDIENCE"):
        monkeypatch.delenv(name, raising=False)

    assert cli.main(["serve"], server=server) == 0
    assert NO_CREDENTIALS_WARNING in capsys.readouterr().err


def test_serve_nao_avisa_com_chave_de_desenvolvimento_nem_imprime_segredo(
    ambiente: Path, monkeypatch: pytest.MonkeyPatch, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    chave = "aic_0123456789abcdef_segredo-dev"
    monkeypatch.setenv("AI_CORE_PROFILE", "memory")
    monkeypatch.setenv("AI_CORE_DEV_API_KEY", chave)

    assert cli.main(["serve"], server=server) == 0
    saida = capsys.readouterr()
    assert NO_CREDENTIALS_WARNING not in saida.err
    assert "segredo-dev" not in saida.out + saida.err


def test_o_perfil_de_teste_nao_avisa(ambiente: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["serve"], server=server)
    assert NO_CREDENTIALS_WARNING not in capsys.readouterr().err


def test_configuracao_invalida_sai_com_codigo_nao_zero_sem_chamar_o_servidor(
    monkeypatch: pytest.MonkeyPatch, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AI_CORE_PROFILE", "producao")

    codigo = cli.main(["serve"], server=server)

    assert codigo == 1
    assert server.calls == []
    assert "AI_CORE_PROFILE" in capsys.readouterr().err


def test_boot_interrompido_sai_com_codigo_nao_zero_sem_chamar_o_servidor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    quebrado = tmp_path / "assistants.yaml"
    quebrado.write_text(ASSISTANTS_YAML_QUEBRADO, encoding="utf-8")
    monkeypatch.setenv("AI_CORE_PROFILE", "test")
    monkeypatch.setenv("AI_CORE_ASSISTANTS_FILE", str(quebrado))

    codigo = cli.main(["serve"], server=server)

    assert codigo == 1
    assert server.calls == []
    assert "boot interrompido" in capsys.readouterr().err


def test_perfil_pode_ser_sobreposto_no_comando(
    ambiente: Path, monkeypatch: pytest.MonkeyPatch, server: FakeServer
) -> None:
    monkeypatch.setenv("AI_CORE_PROFILE", "memory")
    assert cli.main(["serve", "--profile", "test"], server=server) == 0


def test_ajuda_lista_o_subcomando(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    assert "serve" in capsys.readouterr().out


def test_sem_subcomando_o_comando_recusa(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main([])


@pytest.mark.us1
def test_pelo_serve_o_sdk_de_mcp_continua_em_info(ambiente: Path) -> None:
    """R30, achado U4 da análise: depois de o servidor assumir o processo, `mcp.*` continua sem registrar em DEBUG."""
    root = logging.getLogger()
    before = root.level
    root.setLevel(logging.DEBUG)
    try:
        assert cli.main(["serve"], server=FakeServer()) == 0
        assert logging.getLogger("mcp.client.sse").getEffectiveLevel() == logging.INFO
    finally:
        root.setLevel(before)
