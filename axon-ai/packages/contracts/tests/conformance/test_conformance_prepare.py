"""Conformidade do hook opcional `prepare` (ADR-041; contratos 0.2.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from packs import make_pack

from axon_ai_contracts import PackContext, PackManifest
from axon_ai_contracts.testing import check_pack


def codes(pack: object, **kwargs: Any) -> list[str]:
    return [issue.code for issue in check_pack(pack, check_distribution=False, **kwargs).issues]


class NoPrepare:
    """Pack completo sem herdar de `PackBase` e sem `prepare`: continua conforme (o `AgentPack` não muda)."""

    name = "bare"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        return PackManifest(name="bare", version="0.1.0")

    def system_prompt(self, ctx: PackContext) -> None:
        return None

    async def prepare_context(self, view: Any, ctx: PackContext) -> dict[str, Any]:
        return {}

    def tools(self, ctx: PackContext) -> tuple[()]:
        return ()

    def retrievers(self, ctx: PackContext) -> tuple[()]:
        return ()

    def reranker(self, ctx: PackContext) -> None:
        return None

    def validators(self, ctx: PackContext) -> tuple[()]:
        return ()


def test_pack_sem_prepare_e_conforme() -> None:
    assert codes(NoPrepare()) == []


def test_default_do_pack_base_e_conforme() -> None:
    assert codes(make_pack()) == []


def test_prepare_chamado_duas_vezes_no_mesmo_diretorio_e_visto_pelo_catalogo() -> None:
    seen: list[tuple[str, Path | None]] = []

    def prepare(self: Any, ctx: PackContext) -> None:
        assert ctx.data_dir is not None and ctx.data_dir.is_dir()
        marker = ctx.data_dir / "modelo.bin"
        if not marker.exists():
            marker.write_bytes(b"x")
        seen.append(("prepare", ctx.data_dir))

    def tools(self: Any, ctx: PackContext) -> tuple[()]:
        assert ctx.data_dir is not None and (ctx.data_dir / "modelo.bin").exists()
        seen.append(("tools", ctx.data_dir))
        return ()

    assert codes(make_pack(prepare=prepare, tools=tools)) == []
    assert [hook for hook, _ in seen] == ["prepare", "prepare", "tools"]
    directories = {directory for _, directory in seen}
    assert len(directories) == 1
    (directory,) = directories
    assert directory is not None and directory.name == "good"
    assert not directory.exists(), "o diretório temporário é apagado no fim"


def test_data_dir_informado_pelo_autor(tmp_path: Path) -> None:
    def prepare(self: Any, ctx: PackContext) -> None:
        assert ctx.data_dir == tmp_path / "dados"
        (tmp_path / "dados" / "ok").touch()

    assert codes(make_pack(prepare=prepare), data_dir=tmp_path / "dados") == []
    assert (tmp_path / "dados" / "ok").exists(), "o diretório do autor fica"


def test_prepare_que_levanta_na_segunda_chamada() -> None:
    calls: list[int] = []

    def prepare(self: Any, ctx: PackContext) -> None:
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("já existe")

    report = check_pack(make_pack(prepare=prepare), check_distribution=False)
    assert [(issue.code, issue.subject) for issue in report.issues] == [("hook.raised", "hook:prepare")]
    assert "RuntimeError: já existe" in report.issues[0].message


def test_prepare_que_devolve_valor() -> None:
    def prepare(self: Any, ctx: PackContext) -> bool:
        return True

    assert codes(make_pack(prepare=prepare)) == ["hook.return_type"]


def test_prepare_assincrono() -> None:
    calls: list[int] = []

    async def prepare(self: Any, ctx: PackContext) -> None:
        calls.append(1)

    assert codes(make_pack(prepare=prepare)) == ["hook.not_sync"]
    assert calls == [], "não é chamado"


def test_falha_no_preparo_nao_encerra_a_suite() -> None:
    def prepare(self: Any, ctx: PackContext) -> None:
        raise OSError("sem rede")

    def system_prompt(self: Any, ctx: PackContext) -> int:
        return 1

    assert codes(make_pack(prepare=prepare, system_prompt=system_prompt)) == ["hook.raised", "hook.return_type"]
