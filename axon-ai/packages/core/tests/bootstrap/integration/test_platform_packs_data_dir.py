"""O boot entrega a cada pack o diretório de dados e nunca o prepara (ADR-041; 011 FR-028, R54; 002 US4 cen. 5)."""

from __future__ import annotations

from pathlib import Path

from bootstrap_testkit import MemoryConfig, write_config

from axon_ai.bootstrap.wiring import platform
from axon_ai.packs.adapters.memory import InMemoryPackSource
from axon_ai_contracts import PackBase, PackContext, PackManifest

PACKS_YAML = "packs:\n  dados:\n    enabled: true\n"
ASSISTANTS_YAML = "assistants:\n  geral:\n    flow: chat\n    packs: [dados]\n    models:\n      generation: ollama/m\n"


def _recording_pack(seen: list[Path | None], prepared: list[int]) -> type[PackBase]:
    class DataPack(PackBase):
        name = "dados"
        contract_version = "0.2.1"

        def manifest(self) -> PackManifest:
            return PackManifest(name="dados", version="0.1.0")

        def system_prompt(self, ctx: PackContext) -> str:
            seen.append(ctx.data_dir)
            return "p"

        def prepare(self, ctx: PackContext) -> None:
            prepared.append(1)

    return DataPack


def test_o_boot_entrega_o_data_dir_e_nao_chama_prepare(tmp_path: Path) -> None:
    seen: list[Path | None] = []
    prepared: list[int] = []
    root = tmp_path / "dados-dos-packs"
    config = write_config(tmp_path, packs=PACKS_YAML, assistants=ASSISTANTS_YAML, packs_data_dir=root)

    plataforma = platform(
        config=MemoryConfig(config), overrides={"pack_source": InMemoryPackSource.of(_recording_pack(seen, prepared))}
    )

    assert seen == [root / "dados"]
    assert prepared == []
    assert not root.exists(), "o boot não cria o diretório (em runtime ele é somente leitura)"
    plataforma.aclose()


def test_sem_raiz_o_data_dir_e_none(tmp_path: Path) -> None:
    seen: list[Path | None] = []
    config = write_config(tmp_path, packs=PACKS_YAML, assistants=ASSISTANTS_YAML)
    plataforma = platform(
        config=MemoryConfig(config), overrides={"pack_source": InMemoryPackSource.of(_recording_pack(seen, []))}
    )
    assert seen == [None]
    plataforma.aclose()
