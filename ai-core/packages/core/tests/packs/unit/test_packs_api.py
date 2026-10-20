"""Value objects e erros dos seams da 002 (T004)."""

from __future__ import annotations

import dataclasses

import pytest

from ai_core.packs.api import (
    Composition,
    CompositionError,
    PackCapabilities,
    PackConfigError,
    PackEntry,
    PackHookError,
    PackStatus,
    RetrieverCapability,
)
from ai_core.packs.ports import PackSettings


def _capabilities() -> PackCapabilities:
    return PackCapabilities(
        system_prompt=True,
        tools=("echo",),
        retrievers=(RetrieverCapability(name="docs", collections=frozenset({"d"})),),
        reranker=False,
        validators=("ok",),
        preferred_flow="chat",
        depends_on=(),
        requires_collections=("d",),
    )


def test_pack_entry_requires_error_message_when_in_error() -> None:
    with pytest.raises(ValueError):
        PackEntry(name="x", version="1", contract_version="0.2", origin="code", status=PackStatus.ERROR)
    entry = PackEntry(
        name="x",
        version="1",
        contract_version="0.2",
        origin="code",
        status=PackStatus.ENABLED,
        capabilities=_capabilities(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.status = PackStatus.DISABLED  # type: ignore[misc]


def test_status_values() -> None:
    assert [status.value for status in PackStatus] == ["enabled", "disabled", "error"]


def test_composition_normalizes_to_tuple() -> None:
    assert Composition(packs=["a", "b"]).packs == ("a", "b")  # type: ignore[arg-type]


def test_errors_carry_context() -> None:
    composition_error = CompositionError("x indisponível", packs=["x", "y"])
    assert composition_error.packs == ("x", "y") and str(composition_error) == "x indisponível"
    hook_error = PackHookError("falhou", pack="p", hook="prepare_context")
    assert (hook_error.pack, hook_error.hook) == ("p", "prepare_context")
    assert isinstance(PackConfigError("x"), ValueError)


def test_pack_settings_defaults_and_read_only_config() -> None:
    settings = PackSettings()
    assert settings.enabled is False and settings.config == {}
    original = {"a": {"b": 1}}
    configured = PackSettings(enabled=True, config=original)
    original["a"]["b"] = 2
    assert configured.config == {"a": {"b": 1}}
    with pytest.raises(TypeError):
        configured.config["a"] = 3  # type: ignore[index]
