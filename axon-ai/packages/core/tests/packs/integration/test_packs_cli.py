"""T034 — `packs list` e `packs check` (US4; contracts/cli.md) sobre a carga real: entry points e `packs.yaml` em disco.

Os comandos leem o mesmo registry que o boot monta, pela mesma rotina de carga — por isso `check` reprova exatamente o
que o servidor marcaria como erro (research R15, R16).
"""

from __future__ import annotations

import io
import textwrap
from pathlib import Path

import pytest
from packs_testkit import GOOD_MODULE, FakeDistributions

from axon_ai.packs.adapters.cli import check_command, config_error_command, list_command
from axon_ai.packs.adapters.config_yaml import YamlPackConfigSource
from axon_ai.packs.adapters.entry_points import EntryPointPackSource
from axon_ai.packs.api import PackConfigError
from axon_ai.packs.service import PackRuntime

OLD_MODULE = """
from axon_ai_contracts import PackBase, PackManifest


class OldPack(PackBase):
    name = "velho"
    contract_version = "0.3"

    def manifest(self):
        return PackManifest(name="velho", version="1.2.0")
"""


def _runtime(tmp_path: Path, fake: FakeDistributions, packs_yaml: str, *, with_old: bool = False) -> PackRuntime:
    fake.add(
        "dist-good",
        version="2.0.1",
        entry_points={"good": "cli_good_mod:GoodPack"},
        modules={"cli_good_mod": GOOD_MODULE},
    )
    if with_old:
        fake.add(
            "dist-velho",
            version="1.2.0",
            entry_points={"velho": "cli_old_mod:OldPack"},
            modules={"cli_old_mod": OLD_MODULE},
        )
    config = tmp_path / "packs.yaml"
    config.write_text(textwrap.dedent(packs_yaml), encoding="utf-8")
    runtime = PackRuntime(EntryPointPackSource(), YamlPackConfigSource(config))
    runtime.load()
    return runtime


GOOD_ENABLED = "packs:\n  good:\n    enabled: true\n    config: {collection: docs}\n"


def _line(out: io.StringIO, name: str) -> str:
    """A linha de um pack. O ambiente de teste também tem o `axon-generic` instalado por entry point — ele aparece como
    mais um pack, desabilitado, e é por isso que as asserções procuram pelo nome."""
    return next(line for line in out.getvalue().splitlines() if line.split()[0] == name)


def test_list_mostra_nome_versao_contrato_e_status(tmp_path: Path, fake_distributions: FakeDistributions) -> None:
    """US4 cen. 1."""
    runtime = _runtime(tmp_path, fake_distributions, GOOD_ENABLED + "  scouting:\n    enabled: true\n")
    out = io.StringIO()

    assert list_command(runtime, out) == 0
    assert len(out.getvalue().splitlines()) == len(runtime.entries())
    assert _line(out, "good").split() == ["good", "2.0.1", "0.2", "enabled"]
    assert _line(out, "scouting").split()[:4] == ["scouting", "-", "-", "error"]
    assert "não instalado" in _line(out, "scouting")


def test_list_sai_com_zero_mesmo_com_pack_em_erro(tmp_path: Path, fake_distributions: FakeDistributions) -> None:
    runtime = _runtime(tmp_path, fake_distributions, GOOD_ENABLED, with_old=True)
    out = io.StringIO()
    assert list_command(runtime, out) == 0
    velho = _line(out, "velho")
    assert "error" in velho and "requer axon-ai-contracts" in velho  # a causa aparece na linha (SC-004)


def test_check_com_todos_bons_sai_com_zero(tmp_path: Path, fake_distributions: FakeDistributions) -> None:
    runtime = _runtime(tmp_path, fake_distributions, GOOD_ENABLED)
    out = io.StringIO()
    assert check_command(runtime, out) == 0
    assert out.getvalue().splitlines() == [f"{len(runtime.entries())} packs ok"]


def test_check_reprova_incompativel_mesmo_desabilitado(tmp_path: Path, fake_distributions: FakeDistributions) -> None:
    """US4 cen. 2: instalado e desligado ainda é incompatível — o build precisa pegar antes que alguém o habilite."""
    runtime = _runtime(tmp_path, fake_distributions, GOOD_ENABLED + "  velho:\n    enabled: false\n", with_old=True)
    out = io.StringIO()

    assert check_command(runtime, out) == 1
    linhas = out.getvalue().splitlines()
    assert len(linhas) == 2  # só a entrada em erro e o resumo
    assert linhas[0].startswith("velho") and "requer axon-ai-contracts>=0.3" in linhas[0]
    assert "good" not in out.getvalue()
    assert linhas[-1] == f"1 de {len(runtime.entries())} packs em erro"


def test_check_nomeia_pack_nao_instalado_e_configuracao_fora_do_schema(
    tmp_path: Path, fake_distributions: FakeDistributions
) -> None:
    runtime = _runtime(
        tmp_path,
        fake_distributions,
        "packs:\n  good:\n    enabled: true\n    config: {collection: 7}\n  scouting:\n    enabled: true\n",
    )
    out = io.StringIO()

    assert check_command(runtime, out) == 1
    texto = out.getvalue()
    assert "good" in texto and "configuração inválida em 'collection'" in texto
    assert "scouting" in texto and "não instalado" in texto
    assert texto.splitlines()[-1] == f"2 de {len(runtime.entries())} packs em erro"


@pytest.mark.parametrize("conteudo", ["packs: [good]\n", "pacotes: {}\n", "packs: {good: {enabled: talvez}}\n"])
def test_packs_yaml_malformado_sai_com_dois(
    tmp_path: Path, fake_distributions: FakeDistributions, conteudo: str
) -> None:
    with pytest.raises(PackConfigError) as caught:
        _runtime(tmp_path, fake_distributions, conteudo)
    err = io.StringIO()
    assert config_error_command(caught.value, err) == 2
    assert str(caught.value) in err.getvalue()
