from __future__ import annotations

import pytest

from ai_core_contracts.pack import RETRIEVAL_FILTERS_KEY, PackContext, PackManifest


def test_manifest_defaults_and_freezing() -> None:
    manifest = PackManifest(name="p", version="0.1.0", depends_on=["a"], config_schema={"type": "object"})
    assert manifest.preferred_flow is None
    assert manifest.depends_on == ("a",)
    assert manifest.requires_collections == ()
    with pytest.raises(TypeError):
        manifest.config_schema["type"] = "array"  # type: ignore[index]


def test_manifest_rejects_text_as_dependency_list() -> None:
    with pytest.raises(TypeError):
        PackManifest(name="p", version="0.1.0", depends_on="abc")


def test_pack_context_has_only_load_data() -> None:
    ctx = PackContext(pack_name="p", config={"collection": "docs"})
    assert ctx.config == {"collection": "docs"}
    with pytest.raises(ValueError):
        PackContext(pack_name="")


def test_retrieval_filters_key() -> None:
    assert RETRIEVAL_FILTERS_KEY == "retrieval_filters"
