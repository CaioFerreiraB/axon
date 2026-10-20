"""Redação de credenciais (spec 009, T006): a tabela de data-model.md, linha por linha (FR-002)."""

from __future__ import annotations

import pytest

from axon_ai.observability.domain.redaction import (
    MAX_TEXT,
    REDACTED,
    SENSITIVE_NAMES,
    redact_text,
    redact_value,
)


@pytest.mark.parametrize("name", sorted(SENSITIVE_NAMES))
def test_sensitive_key_is_redacted(name: str) -> None:
    assert redact_value({name: "sk-abc123"}) == {name: REDACTED}


@pytest.mark.parametrize("spelling", ["Authorization", "API_KEY", "api-key", "Access-Token", "SET-COOKIE"])
def test_key_comparison_ignores_case_and_separators(spelling: str) -> None:
    assert redact_value({spelling: "segredo"}) == {spelling: REDACTED}


def test_nested_structures_are_redacted() -> None:
    value = {"headers": [{"authorization": "Bearer sk-1"}, {"accept": "application/json"}], "ok": True}
    assert redact_value(value) == {
        "headers": [{"authorization": REDACTED}, {"accept": "application/json"}],
        "ok": True,
    }


def test_non_sensitive_values_pass_through() -> None:
    value = {"model": "qwen3:1.7b", "tokens": 412, "flags": ["a"], "nada": None}
    assert redact_value(value) == value


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("falhou: Bearer sk-abc123", f"falhou: Bearer {REDACTED}"),
        ("bearer sk-abc123", f"bearer {REDACTED}"),
        ("GET /v1?api_key=sk-1&x=2", f"GET /v1?api_key={REDACTED}&x=2"),
        ("{'Authorization': 'Bearer sk-1'}", f"{{'Authorization': 'Bearer {REDACTED}'}}"),
        ("password: hunter2", f"password: {REDACTED}"),
        ("token=abc", f"token={REDACTED}"),
        ("https://user:s3nha@api.exemplo/v1", f"https://user:{REDACTED}@api.exemplo/v1"),
        ("timeout após 30s", "timeout após 30s"),
    ],
)
def test_free_text_patterns(text: str, expected: str) -> None:
    assert redact_text(text) == expected


def test_long_text_is_truncated_with_a_mark() -> None:
    assert redact_text("a" * MAX_TEXT) == "a" * MAX_TEXT
    truncated = redact_text("a" * (MAX_TEXT + 5))
    assert truncated.startswith("a" * MAX_TEXT)
    assert truncated.endswith("… [truncado: 5 caracteres]")


def test_text_inside_structures_is_also_redacted() -> None:
    assert redact_value({"message": "Bearer sk-1"}) == {"message": f"Bearer {REDACTED}"}


def test_redaction_is_idempotent() -> None:
    value = {"authorization": "Bearer sk-1", "message": "api_key=sk-2", "url": "https://u:p@h/v1"}
    once = redact_value(value)
    assert redact_value(once) == once
