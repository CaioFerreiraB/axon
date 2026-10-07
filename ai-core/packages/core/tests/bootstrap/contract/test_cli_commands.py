"""T031 — a raiz `ai-core` e os subcomandos dos módulos (contracts/cli.md; US4).

Cada comando por `main(argv)`, com a saída capturada e o servidor injetado — que nenhum subcomando além de `serve`
pode chamar (FR-011).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from bootstrap_testkit import (
    ASSISTANTS_YAML,
    ASSISTANTS_YAML_QUEBRADO,
    ASSISTANTS_YAML_SEM_PACK,
    PACKS_YAML,
    PACKS_YAML_COM_QUEBRADO,
    FakeServer,
)

from ai_core.bootstrap import cli
from ai_core.bootstrap.profiles import TEST_API_KEY

PACKS_YAML_MALFORMADO: Final = "pacotes: {}\n"
UNREACHABLE: Final = "postgresql://ai:segredo-do-banco@127.0.0.1:1/ai"

SUBCOMANDOS: Final = ("serve", "packs", "assistants", "keys", "health", "audit")

Configurar = Callable[..., None]
Cap = pytest.CaptureFixture[str]


@pytest.fixture
def configurar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Configurar:
    """Escreve os dois arquivos, aponta as variáveis para eles e sobe no perfil de teste."""
    for name in ("AI_CORE_DEV_API_KEY", "AI_CORE_OIDC_ISSUER", "AI_CORE_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)

    def write(*, packs: str = PACKS_YAML, assistants: str = ASSISTANTS_YAML, profile: str = "test") -> None:
        (tmp_path / "packs.yaml").write_text(packs, encoding="utf-8")
        (tmp_path / "assistants.yaml").write_text(assistants, encoding="utf-8")
        monkeypatch.setenv("AI_CORE_PROFILE", profile)
        monkeypatch.setenv("AI_CORE_PACKS_FILE", str(tmp_path / "packs.yaml"))
        monkeypatch.setenv("AI_CORE_ASSISTANTS_FILE", str(tmp_path / "assistants.yaml"))

    return write


def run(argv: list[str], server: FakeServer) -> int:
    codigo = cli.main(argv, server=server)
    assert server.calls == [], f"{argv}: só `serve` abre a API"
    return codigo


# --- raiz -------------------------------------------------------------------------------------------------------------


def test_ajuda_lista_todos_os_subcomandos(capsys: Cap) -> None:
    """US4 cen. 1."""
    with pytest.raises(SystemExit) as saida:
        cli.main(["--help"])
    assert saida.value.code == 0
    ajuda = capsys.readouterr().out
    for subcomando in SUBCOMANDOS:
        assert subcomando in ajuda, subcomando


@pytest.mark.parametrize(("grupo", "filhos"), [("packs", ("list", "check")), ("keys", ("create", "list", "revoke"))])
def test_ajuda_de_cada_grupo_lista_os_comandos_do_modulo(grupo: str, filhos: tuple[str, ...], capsys: Cap) -> None:
    with pytest.raises(SystemExit):
        cli.main([grupo, "--help"])
    ajuda = capsys.readouterr().out
    for filho in filhos:
        assert filho in ajuda


def test_os_comandos_vem_de_uma_lista_de_registro() -> None:
    """US4 cen. 3: acrescentar os comandos de um módulo é acrescentar entradas à lista, sem tocar nos outros."""
    caminhos = {command.path for command in cli.COMMANDS}
    assert caminhos == {
        ("serve",),
        ("packs", "list"),
        ("packs", "check"),
        ("assistants", "validate"),
        ("keys", "create"),
        ("keys", "list"),
        ("keys", "revoke"),
        ("health",),
        ("audit",),
    }


def test_erro_de_configuracao_sai_com_1_nomeando_a_variavel(
    configurar: Configurar, monkeypatch: pytest.MonkeyPatch, server: FakeServer, capsys: Cap
) -> None:
    configurar()
    monkeypatch.setenv("AI_CORE_PORT", "abc")
    for argv in (["packs", "list"], ["assistants", "validate"], ["keys", "list"], ["health"]):
        assert run(argv, server) == 1, argv
        assert "AI_CORE_PORT" in capsys.readouterr().err


# --- packs (002) ------------------------------------------------------------------------------------------------------


def test_packs_list_sai_com_0(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar()
    assert run(["packs", "list"], server) == 0
    assert "generic" in capsys.readouterr().out


def test_packs_check_com_pack_em_erro_sai_com_1(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar(packs=PACKS_YAML_COM_QUEBRADO)
    assert run(["packs", "check"], server) == 1
    assert "inexistente" in capsys.readouterr().out


def test_packs_check_sem_erro_sai_com_0(configurar: Configurar, server: FakeServer) -> None:
    configurar()
    assert run(["packs", "check"], server) == 0


def test_packs_yaml_malformado_sai_com_2(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar(packs=PACKS_YAML_MALFORMADO)
    for argv in (["packs", "list"], ["packs", "check"]):
        assert run(argv, server) == 2
        assert "packs.yaml inválido" in capsys.readouterr().err


# --- assistants validate (003) ----------------------------------------------------------------------------------------


def test_assistants_validate_tudo_disponivel_sai_com_0(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar()
    assert run(["assistants", "validate"], server) == 0
    assert "geral" in capsys.readouterr().out


def test_assistants_validate_com_assistant_indisponivel_sai_com_1(
    configurar: Configurar, server: FakeServer, capsys: Cap
) -> None:
    """US4 cen. 2 e Independent Test."""
    configurar(packs=PACKS_YAML_COM_QUEBRADO, assistants=ASSISTANTS_YAML_SEM_PACK)
    assert run(["assistants", "validate"], server) == 1
    saida = capsys.readouterr().out
    assert "orfao" in saida and "inexistente" in saida


def test_assistants_yaml_malformado_sai_com_2(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar(assistants=ASSISTANTS_YAML_QUEBRADO)
    assert run(["assistants", "validate"], server) == 2
    assert "assistants.yaml inválido" in capsys.readouterr().err


# --- keys (003) -------------------------------------------------------------------------------------------------------


def test_keys_create_imprime_a_chave_e_avisa_que_o_perfil_nao_e_persistente(
    configurar: Configurar, server: FakeServer, capsys: Cap
) -> None:
    configurar()
    assert run(["keys", "create", "--subject", "user:caio", "--group", "admin", "--label", "notebook"], server) == 0
    saida = capsys.readouterr()
    assert saida.out.strip().splitlines()[-1].startswith("aic_"), "a chave sai sozinha na última linha"
    assert "subject: user:caio" in saida.out and "notebook" in saida.out
    assert "não tem armazenamento persistente" in saida.err


def test_keys_list_mostra_so_o_que_se_pode_mostrar(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar()
    assert run(["keys", "list"], server) == 0
    saida = capsys.readouterr().out
    assert "7e57c0de00000001" in saida, "a chave semeada do perfil de teste"
    assert TEST_API_KEY not in saida


def test_keys_revoke_de_chave_inexistente_sai_com_1(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar()
    assert run(["keys", "revoke", "ffffffffffffffff"], server) == 1
    assert "não existe" in capsys.readouterr().err


def test_keys_revoke_da_chave_semeada(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar()
    assert run(["keys", "revoke", "7e57c0de00000001"], server) == 0
    assert "revogada: 7e57c0de00000001" in capsys.readouterr().out


def test_keys_create_exige_subject(configurar: Configurar, server: FakeServer) -> None:
    configurar()
    with pytest.raises(SystemExit):
        cli.main(["keys", "create"], server=server)


# --- health (011) -----------------------------------------------------------------------------------------------------


def test_health_ok_sai_com_0_e_um_item_por_linha(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar()
    assert run(["health"], server) == 0
    saida = capsys.readouterr().out
    for item in ("boot:configuration", "pack:generic", "assistant:geral", "model:ollama/qwen3:1.7b"):
        assert item in saida
    assert saida.strip().splitlines()[-1] == "status: ok"


def test_health_degradado_sai_com_1(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar(packs=PACKS_YAML_COM_QUEBRADO, assistants=ASSISTANTS_YAML_SEM_PACK)
    assert run(["health"], server) == 1
    saida = capsys.readouterr().out
    assert "pack:inexistente" in saida and saida.strip().splitlines()[-1] == "status: degraded"


def test_health_com_banco_inacessivel_sai_com_2_sem_expor_a_url(
    configurar: Configurar, monkeypatch: pytest.MonkeyPatch, server: FakeServer, capsys: Cap
) -> None:
    configurar(profile="persistent")
    monkeypatch.setenv("AI_CORE_DATABASE_URL", UNREACHABLE)
    assert run(["health"], server) == 2
    saida = capsys.readouterr()
    texto = saida.out + saida.err
    assert "database" in texto and "status: down" in saida.out
    assert UNREACHABLE not in texto and "segredo-do-banco" not in texto


def test_keys_com_banco_inacessivel_sai_com_1_sem_expor_a_url(
    configurar: Configurar, monkeypatch: pytest.MonkeyPatch, server: FakeServer, capsys: Cap
) -> None:
    configurar(profile="persistent")
    monkeypatch.setenv("AI_CORE_DATABASE_URL", UNREACHABLE)
    assert run(["keys", "list"], server) == 1
    saida = capsys.readouterr()
    assert "database" in saida.err
    assert "segredo-do-banco" not in saida.out + saida.err


def test_profile_vale_para_todos_os_subcomandos(
    configurar: Configurar, monkeypatch: pytest.MonkeyPatch, server: FakeServer
) -> None:
    configurar(profile="memory")
    assert run(["keys", "list", "--profile", "test"], server) == 0
    assert run(["packs", "list", "--profile", "test"], server) == 0


# --- audit (004; Fase 3, T048; contracts/cli.md, "Fase 3") -----------------------------------------------------------


@pytest.mark.us4
def test_audit_com_data_fora_do_iso_sai_com_2(configurar: Configurar, server: FakeServer, capsys: Cap) -> None:
    configurar()
    assert run(["audit", "--since", "ontem"], server) == 2
    assert "since" in capsys.readouterr().err


@pytest.mark.us4
def test_audit_no_perfil_de_teste_sai_com_0_e_sem_registros(
    configurar: Configurar, server: FakeServer, capsys: Cap
) -> None:
    configurar()
    assert run(["audit", "--limit", "10"], server) == 0
    assert capsys.readouterr().out.strip() == ""
