"""check_declaration: regras de identidade e manifest (T015)."""

from __future__ import annotations

from axon_ai_contracts import PackManifest
from axon_ai_contracts.declaration import check_declaration


def _codes(**kwargs: object) -> list[str]:
    params: dict[str, object] = {
        "pack_name": "meu_pack",
        "contract_version": "0.2",
        "manifest": PackManifest(name="meu_pack", version="0.1.0"),
    }
    params.update(kwargs)
    return [issue.code for issue in check_declaration(**params)]  # type: ignore[arg-type]


def test_valid_declaration_has_no_issues() -> None:
    assert _codes() == []


def test_invalid_pack_name() -> None:
    assert _codes(pack_name="Meu-Pack", manifest=PackManifest(name="Meu-Pack", version="0.1.0")) == [
        "pack.name.invalid"
    ]
    assert "pack.name.invalid" in _codes(pack_name="a" * 33, manifest=PackManifest(name="a" * 33, version="1.0"))


def test_invalid_contract_version() -> None:
    assert _codes(contract_version="1") == ["pack.contract_version.invalid"]
    assert _codes(contract_version="0.1rc1") == ["pack.contract_version.invalid"]


def test_manifest_type_and_name() -> None:
    assert _codes(manifest={"name": "meu_pack"}) == ["manifest.type"]
    assert _codes(manifest=PackManifest(name="outro", version="0.1.0")) == ["manifest.name_mismatch"]


def test_manifest_version() -> None:
    assert _codes(manifest=PackManifest(name="meu_pack", version="v1")) == ["manifest.version.invalid"]


def test_preferred_flow_must_not_be_empty() -> None:
    assert _codes(manifest=PackManifest(name="meu_pack", version="0.1.0", preferred_flow=" ")) == [
        "manifest.preferred_flow.invalid"
    ]


def test_dependencies() -> None:
    self_dep = PackManifest(name="meu_pack", version="0.1.0", depends_on=("meu_pack",))
    assert _codes(manifest=self_dep) == ["manifest.self_dependency"]
    duplicated = PackManifest(name="meu_pack", version="0.1.0", depends_on=("outro", "outro"))
    assert _codes(manifest=duplicated) == ["manifest.duplicate_dependency"]


def test_duplicated_collection() -> None:
    manifest = PackManifest(name="meu_pack", version="0.1.0", requires_collections=("docs", "docs"))
    assert _codes(manifest=manifest) == ["manifest.duplicate_collection"]


def test_config_schema_structure() -> None:
    not_json = PackManifest(name="meu_pack", version="0.1.0", config_schema={"default": object()})  # type: ignore[dict-item]
    assert _codes(manifest=not_json) == ["manifest.config_schema.invalid"]
    bad_required = PackManifest(
        name="meu_pack",
        version="0.1.0",
        config_schema={"type": "object", "properties": {"a": {"type": "string"}}, "required": ["b"]},
    )
    assert _codes(manifest=bad_required) == ["manifest.config_schema.invalid"]
    valid = PackManifest(
        name="meu_pack",
        version="0.1.0",
        config_schema={"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
    )
    assert _codes(manifest=valid) == []


def test_issues_name_the_subject() -> None:
    [issue] = check_declaration(
        pack_name="meu_pack", contract_version="0.2", manifest=PackManifest(name="outro", version="0.1.0")
    )
    assert issue.subject == "manifest"
    assert "outro" in issue.message and issue.severity == "error"
