"""Carga do pack `ai-generic` real pelo Pack Runtime (spec 010 US1 cenário 1 e SC-002; quickstart §3).

O pack é uma dependência de desenvolvimento do workspace (010 R8) e é descoberto pelo mesmo `EntryPointPackSource` de
qualquer pack externo: nenhuma distribuição falsa, nenhum caso especial para o nome `generic` no código do core.
"""

from __future__ import annotations

from ai_core.packs.adapters.entry_points import EntryPointPackSource
from ai_core.packs.adapters.memory import InMemoryPackConfigSource
from ai_core.packs.api import PackStatus
from ai_core.packs.ports import PackSettings
from ai_core.packs.service import PackRuntime


def _runtime(settings: dict[str, PackSettings]) -> PackRuntime:
    runtime = PackRuntime(EntryPointPackSource(), InMemoryPackConfigSource(settings))
    runtime.load()
    return runtime


def test_generic_is_discovered_among_the_installed_entry_points() -> None:
    discovered = {pack.name: pack for pack in EntryPointPackSource().discover()}
    assert "generic" in discovered
    assert discovered["generic"].distribution == "ai-generic"
    assert discovered["generic"].version == "0.1.0"


def test_enabled_generic_pack_is_loaded_with_its_capabilities() -> None:
    entry = _runtime({"generic": PackSettings(enabled=True)}).entry("generic")
    assert entry is not None, "o pack instalado precisa aparecer no registry"
    assert entry.status is PackStatus.ENABLED, entry.error
    assert (entry.origin, entry.version, entry.contract_version) == ("code", "0.1.0", "0.2")
    capabilities = entry.capabilities
    assert capabilities is not None
    assert capabilities.system_prompt is True
    assert capabilities.tools == ("calculate",)
    assert capabilities.validators == ("non_empty_answer",)
    assert capabilities.retrievers == ()
    assert capabilities.reranker is False
    assert capabilities.preferred_flow is None
    assert capabilities.depends_on == ()
    assert capabilities.requires_collections == ()


def test_generic_pack_absent_from_the_configuration_is_disabled() -> None:
    entry = _runtime({}).entry("generic")
    assert entry is not None and entry.status is PackStatus.DISABLED
    assert entry.capabilities is None


def test_generic_pack_composes_alone() -> None:
    composition = _runtime({"generic": PackSettings(enabled=True)}).compose(["generic"])
    assert composition.packs == ("generic",)
