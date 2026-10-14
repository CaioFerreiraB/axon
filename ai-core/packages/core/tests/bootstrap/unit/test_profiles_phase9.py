"""T054 — as portas da Fase 9 nos três perfis (research R38, R39): sobreposições da 003, armazenamentos e transporte
do Langfuse da 009 e as `identity_*` da 012."""

from __future__ import annotations

from typing import Any

import pytest

from ai_core.assistants.adapters.memory import InMemorySystemOverrideStore
from ai_core.assistants.adapters.overrides_postgres import PostgresSystemOverrideStore
from ai_core.bootstrap.profiles import (
    PROFILES,
    REQUIRED_PORTS,
    STORAGE_PORTS,
    check_overrides,
    profile_for,
)
from ai_core.bootstrap.settings import ConfigurationError, Settings
from ai_core.observability.adapters.langfuse import OtelLangfuseTransport
from ai_core.observability.adapters.memory import (
    InMemoryDestinationSettingsStore,
    InMemoryPriceStore,
    InMemoryUsageStore,
    RecordingLangfuseTransport,
)
from ai_core.observability.adapters.postgres import (
    PostgresDestinationSettingsStore,
    PostgresPriceStore,
    PostgresUsageStore,
)

STORES = ("system_overrides", "usage_store", "price_store", "destination_settings")
IDENTITY_STORES = ("identity_accounts", "identity_grants", "identity_keys", "identity_settings")


def test_portas_novas_exigidas_e_de_armazenamento() -> None:
    assert {*STORES, "langfuse_transport", *IDENTITY_STORES, "identity_attempts"} <= set(REQUIRED_PORTS)
    assert {*STORES, *IDENTITY_STORES} <= set(STORAGE_PORTS)
    assert "langfuse_transport" not in STORAGE_PORTS and "identity_attempts" not in STORAGE_PORTS
    for name in PROFILES:
        profile_for(name)  # nenhum perfil fica sem fábrica


@pytest.mark.parametrize("name", ["memory", "test"])
def test_memoria_no_memory_e_no_test(name: str) -> None:
    profile = profile_for(name)
    built = {port: profile.build(port, Settings(profile=name), {}) for port in STORES}
    assert isinstance(built["system_overrides"], InMemorySystemOverrideStore)
    assert isinstance(built["usage_store"], InMemoryUsageStore)
    assert isinstance(built["price_store"], InMemoryPriceStore)
    assert isinstance(built["destination_settings"], InMemoryDestinationSettingsStore)


def test_postgres_no_persistent() -> None:
    profile = profile_for("persistent")
    settings = Settings(profile="persistent", database_url="postgresql://x")
    parts: dict[str, Any] = {"database": object()}
    assert isinstance(profile.build("system_overrides", settings, parts), PostgresSystemOverrideStore)
    assert isinstance(profile.build("usage_store", settings, parts), PostgresUsageStore)
    assert isinstance(profile.build("price_store", settings, parts), PostgresPriceStore)
    assert isinstance(profile.build("destination_settings", settings, parts), PostgresDestinationSettingsStore)


def test_langfuse_de_verdade_fora_do_test() -> None:
    assert isinstance(profile_for("memory").build("langfuse_transport", Settings(), {}), OtelLangfuseTransport)
    persistent = Settings(profile="persistent", database_url="postgresql://x")
    assert isinstance(profile_for("persistent").build("langfuse_transport", persistent, {}), OtelLangfuseTransport)
    assert isinstance(
        profile_for("test").build("langfuse_transport", Settings(profile="test"), {}), RecordingLangfuseTransport
    )


def test_o_transporte_se_troca_e_os_armazenamentos_nao() -> None:
    check_overrides({"langfuse_transport": RecordingLangfuseTransport()})
    for port in STORES:
        with pytest.raises(ConfigurationError, match=port):
            check_overrides({port: object()})
