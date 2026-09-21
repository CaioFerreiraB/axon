"""T011b — o comando `ai-core serve` (contracts/boot-sequence.md).

O servidor entra por parâmetro, então o comando é exercitado inteiro sem abrir porta.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bootstrap_testkit import ASSISTANTS_YAML, PACKS_YAML, FakeServer

from ai_core.bootstrap import cli
from ai_core.bootstrap.profiles import ANONYMOUS_WARNING


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
    for etapa in ("configuration", "adapters", "packs", "engine", "api"):
        assert etapa in saida
    assert "9123" in saida


def test_serve_avisa_que_a_autenticacao_e_anonima(
    ambiente: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    """O perfil que mais parece produção é o que não tem autenticação; o aviso evita o engano caro."""
    cli.main(["serve"], server=server)

    assert ANONYMOUS_WARNING in capsys.readouterr().err


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
    quebrado.write_text("assistants:\n  x:\n    models: {}\n", encoding="utf-8")
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
