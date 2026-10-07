"""Suíte de conformidade: forma, identidade, manifest e execução (T016)."""

from __future__ import annotations

from typing import Any

import pytest
from packs import GoodPack, NotAPack, SyncPreparePack, make_pack

from ai_core_contracts import PackManifest
from ai_core_contracts.testing import acheck_pack, assert_pack_conforms, check_pack


def _codes(pack: object, **kwargs: Any) -> list[str]:
    report = check_pack(pack, check_distribution=False, **kwargs)
    return [issue.code for issue in report.issues]


def test_good_pack_conforms() -> None:
    report = check_pack(GoodPack(), check_distribution=False)
    assert report.ok
    assert report.issues == ()
    assert report.pack_name == "good"


def test_object_without_pack_shape() -> None:
    codes = _codes(NotAPack())
    assert codes and set(codes) == {"hook.missing"}


def test_sync_prepare_context() -> None:
    assert _codes(SyncPreparePack()) == ["hook.not_async"]


def test_identity_issues() -> None:
    bad_name = make_pack(name="Meu-Pack", manifest=PackManifest(name="Meu-Pack", version="0.1.0"))
    assert _codes(bad_name) == ["pack.name.invalid"]
    assert _codes(make_pack(contract_version="1")) == ["pack.contract_version.invalid"]


def test_incompatible_contract_version_names_constraint_and_installed() -> None:
    report = check_pack(make_pack(contract_version="0.2"), check_distribution=False)
    [issue] = report.issues
    assert issue.code == "pack.contract_version.incompatible"
    assert issue.message == "requer ai-core-contracts>=0.2, instalado 0.1.1"


def test_manifest_issues_are_reported() -> None:
    assert _codes(make_pack(manifest=PackManifest(name="outro", version="0.1.0"))) == ["manifest.name_mismatch"]
    self_dep = PackManifest(name="good", version="0.1.0", depends_on=("good",))
    assert _codes(make_pack(manifest=self_dep)) == ["manifest.self_dependency"]
    bad_schema = PackManifest(name="good", version="0.1.0", config_schema={"required": "a"})
    assert _codes(make_pack(manifest=bad_schema)) == ["manifest.config_schema.invalid"]


def test_raising_hook_is_reported() -> None:
    def explode(self: Any) -> PackManifest:
        raise RuntimeError("falhou")

    report = check_pack(make_pack(manifest=explode), check_distribution=False)
    [issue] = report.issues
    assert issue.code == "hook.raised"
    assert issue.subject == "hook:manifest"
    assert "falhou" in issue.message


def test_failing_step_stops_dependent_steps() -> None:
    calls: list[str] = []

    def tools(self: Any, ctx: Any) -> tuple[()]:
        calls.append("tools")
        return ()

    pack = make_pack(manifest=PackManifest(name="outro", version="0.1.0"), tools=tools)
    assert _codes(pack) == ["manifest.name_mismatch"]
    assert calls == []


def test_assert_pack_conforms_raises_with_report() -> None:
    with pytest.raises(AssertionError) as excinfo:
        assert_pack_conforms(make_pack(contract_version="1"), check_distribution=False)
    assert "pack.contract_version.invalid" in str(excinfo.value)
    assert_pack_conforms(GoodPack(), check_distribution=False)


def test_render_lists_one_issue_per_line() -> None:
    report = check_pack(NotAPack(), check_distribution=False)
    rendered = report.render()
    assert rendered.count("hook.missing") == len(report.issues)


async def test_check_pack_inside_running_loop_suggests_async_variant() -> None:
    with pytest.raises(RuntimeError, match="acheck_pack"):
        check_pack(GoodPack())
    report = await acheck_pack(GoodPack(), check_distribution=False)
    assert report.ok
