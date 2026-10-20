"""T033 — a allowlist da resolução (003) e a do Model Router (006) dão a mesma resposta (research R5).

As duas linhas de defesa não podem divergir. A regra da 006 é importada só aqui, pela suíte: o código da 003 nunca
importa internals da 006.
"""

from __future__ import annotations

import pytest

from axon_ai.assistants.domain.definitions import allowed_model
from axon_ai.llm.api import ModelRef
from axon_ai.llm.domain.policy import is_allowed

CASOS = [
    ("ollama/qwen3:1.7b", ["ollama/*"]),
    ("ollama/qwen3:1.7b", ["ollama/qwen3:*"]),
    ("ollama/qwen3:1.7b", ["ollama/qwen3:8b"]),
    ("openai/gpt-4o", ["ollama/*"]),
    ("openai/gpt-4o", ["openai/gpt-4*", "ollama/*"]),
    ("openrouter/qwen/qwen3-8b", ["openrouter/*"]),
    ("openrouter/qwen/qwen3-8b", ["openrouter/qwen/*"]),
    ("openrouter/qwen/qwen3-8b", ["openrouter/meta/*"]),
    ("Ollama/Qwen3", ["ollama/*"]),
    ("ollama/Qwen3", ["ollama/qwen3"]),
    ("ollama/qwen3", ["*"]),
    ("ollama/qwen3", ["ollama/qwen?"]),
    ("ollama/qwen3", ["ollama/qwen[0-9]"]),
    ("ollama/q", ["ollama/q", "x/*"]),
]


@pytest.mark.parametrize(("ref", "patterns"), CASOS)
def test_as_duas_regras_concordam(ref: str, patterns: list[str]) -> None:
    parsed = ModelRef.parse(ref)
    assert allowed_model(parsed, patterns) == is_allowed(parsed, patterns)
