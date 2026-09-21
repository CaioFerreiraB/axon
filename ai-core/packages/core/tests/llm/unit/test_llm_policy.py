"""T009 — regras puras de resolução e allowlist (`domain/policy.py`)."""

from __future__ import annotations

import pytest
from llm_testkit import policy

from ai_core.llm.api import ModelNotAllowed, ModelRef, RoleNotConfigured
from ai_core.llm.domain.policy import ensure_allowed, is_allowed, resolve


def test_resolve_devolve_o_modelo_do_papel() -> None:
    assert resolve(policy(), "generation") == ModelRef.parse("ollama/qwen3:1.7b")


def test_resolve_informa_papel_nao_configurado_em_vez_de_escolher() -> None:
    with pytest.raises(RoleNotConfigured) as error:
        resolve(policy(), "rerank")
    assert "rerank" in str(error.value)
    assert "generation" in str(error.value)


@pytest.mark.parametrize(
    ("ref", "patterns", "expected"),
    [
        ("ollama/qwen3:1.7b", ("ollama/*",), True),
        ("openai/gpt-4o", ("ollama/*",), False),
        ("openrouter/qwen/qwen3-8b", ("openrouter/qwen/*",), True),
        ("openrouter/meta/llama", ("openrouter/qwen/*",), False),
        ("ollama/qwen3:1.7b", ("openai/*", "ollama/qwen3:*"), True),
        ("ollama/qwen3:1.7b", (), True),
    ],
)
def test_allowlist(ref: str, patterns: tuple[str, ...], expected: bool) -> None:
    assert is_allowed(ModelRef.parse(ref), patterns) is expected


def test_allowlist_vazia_significa_sem_restricao_declarada() -> None:
    """Research R9: o campo existe desde a Fase 1; vazio é ausência de restrição, não bloqueio total."""
    assert is_allowed(ModelRef.parse("openai/gpt-4o"), ()) is True


def test_ensure_allowed_devolve_a_referencia_quando_permitida() -> None:
    ref = ModelRef.parse("ollama/qwen3:1.7b")
    assert ensure_allowed(ref, ("ollama/*",)) is ref


def test_ensure_allowed_nomeia_referencia_e_padroes() -> None:
    with pytest.raises(ModelNotAllowed) as error:
        ensure_allowed(ModelRef.parse("openai/gpt-4o"), ("ollama/*",))
    assert "openai/gpt-4o" in str(error.value)
    assert "ollama/*" in str(error.value)
