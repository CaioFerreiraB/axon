"""Suíte de conformidade da porta `PackDataDirs` (contracts/ports.md; ADR-041, research R62)."""

from __future__ import annotations

from pathlib import Path

from axon_ai.packs.adapters.data_dirs import LocalPackDataDirs
from axon_ai.packs.ports import PackDataDirs


def test_sem_raiz_nao_ha_diretorio(tmp_path: Path) -> None:
    dirs: PackDataDirs = LocalPackDataDirs(None)
    assert dirs.path("good") is None
    assert dirs.create("good") is None


def test_path_nao_toca_o_disco(tmp_path: Path) -> None:
    root = tmp_path / "dados"
    dirs: PackDataDirs = LocalPackDataDirs(root)
    assert dirs.path("good") == root / "good"
    assert not root.exists()


def test_create_cria_com_os_pais_e_e_idempotente(tmp_path: Path) -> None:
    root = tmp_path / "a" / "b"
    dirs: PackDataDirs = LocalPackDataDirs(root)
    assert dirs.create("good") == root / "good"
    (root / "good" / "modelo.bin").write_bytes(b"x")
    assert dirs.create("good") == root / "good"
    assert (root / "good" / "modelo.bin").read_bytes() == b"x", "criar de novo não apaga o que já existe"
    assert dirs.path("good") == dirs.create("good")
