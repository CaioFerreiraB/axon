"""Regras puras de identidade (FR-017) e de configuração (FR-004) (T010)."""

from __future__ import annotations

from packs_testkit import GOOD_SCHEMA, make_pack_class

from ai_core.packs.domain.config import config_error
from ai_core.packs.domain.identity import read_identity


def test_identity_from_class_attributes() -> None:
    assert read_identity("good", make_pack_class("good", "0.2")) == ("good", "0.2")


def test_name_must_match_entry_point() -> None:
    assert read_identity("outro", make_pack_class("good")) == "entry point 'outro' aponta para classe com name 'good'"


def test_missing_class_attributes() -> None:
    assert read_identity("good", make_pack_class(None)) == "classe sem atributo de classe 'name'"
    assert read_identity("good", make_pack_class("good", None)) == "classe sem atributo de classe 'contract_version'"


def test_instance_only_attribute_is_not_enough() -> None:
    class InstanceOnly:
        def __init__(self) -> None:
            self.name = "good"
            self.contract_version = "0.2"

    assert read_identity("good", InstanceOnly) == "classe sem atributo de classe 'name'"


def test_entry_point_must_point_to_a_class() -> None:
    assert read_identity("good", object()) == "entry point 'good' não aponta para uma classe"


def test_config_conforming_to_schema() -> None:
    assert config_error({"collection": "docs"}, GOOD_SCHEMA) is None
    assert config_error({"qualquer": 1}, None) is None


def test_config_error_names_the_field() -> None:
    message = config_error({"collection": 42}, GOOD_SCHEMA)
    assert message is not None and message.startswith("configuração inválida em 'collection':")
    nested = config_error({"collection": "d", "limits": {"top_k": "x"}}, GOOD_SCHEMA)
    assert nested is not None and nested.startswith("configuração inválida em 'limits.top_k':")
    missing = config_error({}, GOOD_SCHEMA)
    assert missing is not None and missing.startswith("configuração inválida em '(raiz)':")


def test_invalid_schema() -> None:
    message = config_error({}, {"type": "objeto-inexistente"})
    assert message is not None and message.startswith("config_schema inválido:")
