"""Suíte do seam de preparo de dados (contracts/pack-runtime-api.md, "Preparo de dados"; ADR-041, research R63)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from packs_testkit import GOOD_CONFIG, make_good_pack, make_pack_class

from axon_ai.packs.adapters.data_dirs import LocalPackDataDirs
from axon_ai.packs.adapters.memory import InMemoryPackConfigSource, InMemoryPackSource
from axon_ai.packs.api import PackConfigError, PackDataPreparation, PackStatus, PreparedPack
from axon_ai.packs.ports import PackSettings
from axon_ai.packs.service import PackRuntime
from axon_ai_contracts import PackContext, PackManifest

Prepare = Callable[[Any, PackContext], None]


def _runtime(
    *packs: object, settings: dict[str, PackSettings], root: Path | None, error: PackConfigError | None = None
) -> PackRuntime:
    return PackRuntime(
        InMemoryPackSource.of(*packs),  # type: ignore[arg-type]
        InMemoryPackConfigSource(settings, error=error),
        LocalPackDataDirs(root),
    )


def _recording(calls: list[PackContext]) -> Prepare:
    def prepare(self: Any, ctx: PackContext) -> None:
        assert ctx.data_dir is None or ctx.data_dir.is_dir(), "o diretório existe antes do hook"
        calls.append(ctx)

    return prepare


def _enabled(**config: Any) -> PackSettings:
    return PackSettings(enabled=True, config=config)


def test_prepara_os_habilitados_em_ordem_de_nome(tmp_path: Path) -> None:
    calls: list[PackContext] = []
    runtime: PackDataPreparation = _runtime(
        make_good_pack("beta", prepare=_recording(calls)),
        make_good_pack("alfa", prepare=_recording(calls)),
        make_good_pack("desligado", prepare=_recording(calls)),
        make_good_pack("ausente", prepare=_recording(calls)),
        settings={
            "beta": _enabled(**GOOD_CONFIG),
            "alfa": _enabled(**GOOD_CONFIG),
            "desligado": PackSettings(enabled=False, config=GOOD_CONFIG),
        },
        root=tmp_path,
    )

    prepared = runtime.prepare_data()

    assert prepared == (
        PreparedPack(name="alfa", data_dir=tmp_path / "alfa"),
        PreparedPack(name="beta", data_dir=tmp_path / "beta"),
    )
    assert all(item.ok for item in prepared)
    assert [(ctx.pack_name, ctx.data_dir, dict(ctx.config)) for ctx in calls] == [
        ("alfa", tmp_path / "alfa", dict(GOOD_CONFIG)),
        ("beta", tmp_path / "beta", dict(GOOD_CONFIG)),
    ]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["alfa", "beta"]


def test_nenhum_hook_de_catalogo_roda(tmp_path: Path) -> None:
    """Os hooks de catálogo podem precisar justamente do que o `prepare` produz (R63)."""

    def tools(self: Any, ctx: PackContext) -> tuple[()]:
        raise AssertionError("tools não roda no preparo")

    calls: list[PackContext] = []
    runtime = _runtime(
        make_good_pack("good", tools=tools, prepare=_recording(calls)),
        settings={"good": _enabled(**GOOD_CONFIG)},
        root=tmp_path,
    )
    assert runtime.prepare_data() == (PreparedPack(name="good", data_dir=tmp_path / "good"),)
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("pack", "settings", "message"),
    [
        (make_good_pack("good"), {"outro": _enabled()}, "não instalado"),
        (make_pack_class("good", "0.3"), {"good": _enabled()}, "requer axon-ai-contracts>=0.3"),
        (make_good_pack("good"), {"good": _enabled(collection=7)}, "configuração inválida em 'collection'"),
    ],
)
def test_falha_antes_do_hook_tem_a_mensagem_da_carga(
    tmp_path: Path, pack: type, settings: dict[str, PackSettings], message: str
) -> None:
    calls: list[PackContext] = []
    pack.prepare = _recording(calls)  # type: ignore[attr-defined]
    (prepared,) = _runtime(pack, settings=settings, root=tmp_path).prepare_data()
    assert not prepared.ok
    assert prepared.error is not None and message in prepared.error
    assert calls == []
    entry = _runtime(pack, settings=settings, root=tmp_path)
    entry.load()
    loaded = entry.entry(prepared.name)
    assert loaded is not None and loaded.status is PackStatus.ERROR and loaded.error == prepared.error


def test_nome_duplicado(tmp_path: Path) -> None:
    runtime = _runtime(
        ("good", make_good_pack("good")), ("good", make_good_pack("good")), settings={"good": _enabled()}, root=tmp_path
    )
    (prepared,) = runtime.prepare_data()
    assert prepared.error is not None and "nome duplicado" in prepared.error


class Bare:
    """Pack fora de `PackBase`, sem `prepare`: só o diretório."""

    name = "bare"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        return PackManifest(name="bare", version="0.1.0")


def test_pack_sem_prepare_so_ganha_o_diretorio(tmp_path: Path) -> None:
    assert _runtime(Bare, settings={"bare": _enabled()}, root=tmp_path).prepare_data() == (
        PreparedPack(name="bare", data_dir=tmp_path / "bare"),
    )
    assert (tmp_path / "bare").is_dir()


def test_prepare_assincrono_nao_e_chamado(tmp_path: Path) -> None:
    calls: list[int] = []

    async def prepare(self: Any, ctx: PackContext) -> None:
        calls.append(1)

    (prepared,) = _runtime(
        make_good_pack("good", prepare=prepare), settings={"good": _enabled(**GOOD_CONFIG)}, root=tmp_path
    ).prepare_data()
    assert prepared.error == "prepare precisa ser síncrono"
    assert calls == []


def test_excecao_de_um_pack_nao_impede_os_demais(tmp_path: Path) -> None:
    def broken(self: Any, ctx: PackContext) -> None:
        raise ConnectionError("falha ao baixar o modelo")

    calls: list[PackContext] = []
    prepared = _runtime(
        make_good_pack("alfa", prepare=broken),
        make_good_pack("beta", prepare=_recording(calls)),
        settings={"alfa": _enabled(**GOOD_CONFIG), "beta": _enabled(**GOOD_CONFIG)},
        root=tmp_path,
    ).prepare_data()
    assert prepared[0] == PreparedPack(
        name="alfa", data_dir=tmp_path / "alfa", error="prepare levantou ConnectionError: falha ao baixar o modelo"
    )
    assert prepared[1].ok and len(calls) == 1


def test_diretorio_que_nao_se_cria(tmp_path: Path) -> None:
    (tmp_path / "arquivo").write_text("x")
    (prepared,) = _runtime(
        make_good_pack("good"), settings={"good": _enabled(**GOOD_CONFIG)}, root=tmp_path / "arquivo"
    ).prepare_data()
    assert prepared.error is not None and prepared.error.startswith("falha ao criar o diretório de dados")


def test_sem_raiz_o_hook_recebe_none(tmp_path: Path) -> None:
    calls: list[PackContext] = []
    runtime = PackRuntime(
        InMemoryPackSource.of(make_good_pack("good", prepare=_recording(calls))),
        InMemoryPackConfigSource({"good": _enabled(**GOOD_CONFIG)}),
    )
    assert runtime.prepare_data() == (PreparedPack(name="good", data_dir=None),)
    assert calls[0].data_dir is None


def test_packs_yaml_malformado_propaga(tmp_path: Path) -> None:
    runtime = _runtime(settings={}, root=tmp_path, error=PackConfigError("packs: precisa ser um mapeamento"))
    with pytest.raises(PackConfigError, match="mapeamento"):
        runtime.prepare_data()


def test_preparo_nao_carrega_o_registry(tmp_path: Path) -> None:
    runtime = _runtime(make_good_pack("good"), settings={"good": _enabled(**GOOD_CONFIG)}, root=tmp_path)
    runtime.prepare_data()
    assert runtime.entries() == ()
    runtime.load()
    entry = runtime.entry("good")
    assert entry is not None and entry.status is PackStatus.ENABLED
