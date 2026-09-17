"""Carga do registry com adapters em memória (US1 cenários 1 a 3; T011)."""

from __future__ import annotations

from typing import Any

import pytest
from packs_testkit import GOOD_CONFIG, load_runtime, make_good_pack

from ai_core.packs.api import PackStatus
from ai_core.packs.ports import PackSettings
from ai_core_contracts import PackContext


def test_enabled_pack_is_instantiated_with_its_config() -> None:
    seen: list[PackContext] = []
    good = make_good_pack(system_prompt=lambda self, ctx: seen.append(ctx) or "prompt")
    runtime: Any = load_runtime(good, settings={"good": PackSettings(enabled=True, config=GOOD_CONFIG)})
    entry = runtime.entry("good")
    assert entry.status is PackStatus.ENABLED and entry.error is None
    assert (entry.version, entry.contract_version, entry.origin) == ("0.1.0", "0.1", "code")
    assert good.created == 1
    assert [ctx.config for ctx in seen] == [GOOD_CONFIG]
    capabilities = entry.capabilities
    assert capabilities.system_prompt is True and capabilities.tools == ("echo",)
    assert capabilities.validators == ("sempre_ok",) and capabilities.reranker is False
    assert capabilities.preferred_flow == "chat" and capabilities.requires_collections == ("docs",)


def test_catalog_hooks_are_called_once() -> None:
    calls: list[str] = []

    def spy(hook: str, result: Any) -> Any:
        def method(self: Any, ctx: PackContext) -> Any:
            calls.append(hook)
            return result

        return method

    good = make_good_pack(
        system_prompt=spy("system_prompt", None),
        tools=spy("tools", ()),
        retrievers=spy("retrievers", ()),
        reranker=spy("reranker", None),
        validators=spy("validators", ()),
    )
    load_runtime(good, settings={"good": PackSettings(enabled=True, config=GOOD_CONFIG)})
    assert sorted(calls) == ["reranker", "retrievers", "system_prompt", "tools", "validators"]


@pytest.mark.parametrize("settings", [{}, {"good": PackSettings(enabled=False, config=GOOD_CONFIG)}])
def test_not_enabled_pack_is_disabled_and_not_instantiated(settings: dict[str, PackSettings]) -> None:
    good = make_good_pack()
    runtime: Any = load_runtime(good, settings=settings)
    entry = runtime.entry("good")
    assert entry.status is PackStatus.DISABLED
    assert entry.contract_version == "0.1" and entry.capabilities is None
    assert good.created == 0


def test_config_violating_schema_names_the_field() -> None:
    runtime: Any = load_runtime(
        make_good_pack(), settings={"good": PackSettings(enabled=True, config={"collection": 1})}
    )
    entry = runtime.entry("good")
    assert entry.status is PackStatus.ERROR
    assert entry.error.startswith("configuração inválida em 'collection':")


def test_entries_are_sorted_and_lookup_works() -> None:
    runtime: Any = load_runtime(make_good_pack("zeta"), make_good_pack("alfa"))
    assert [entry.name for entry in runtime.entries()] == ["alfa", "zeta"]
    assert runtime.entry("inexistente") is None


def test_registry_is_loaded_once() -> None:
    runtime: Any = load_runtime(make_good_pack())
    with pytest.raises(RuntimeError, match="restart"):
        runtime.load()
