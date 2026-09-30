"""T021 — conformidade da porta `TokenGenerator` (contracts/ports.md)."""

from __future__ import annotations

import re

from ai_core.assistants.adapters.memory import SequentialTokenGenerator
from ai_core.assistants.adapters.tokens import SecretsTokenGenerator


def test_secrets_hex_tem_o_tamanho_e_o_alfabeto() -> None:
    gerador = SecretsTokenGenerator()
    valor = gerador.token_hex(8)
    assert re.fullmatch(r"[0-9a-f]{16}", valor)
    assert gerador.token_hex(8) != valor


def test_secrets_urlsafe_tem_entropia_e_alfabeto_de_url() -> None:
    gerador = SecretsTokenGenerator()
    valor = gerador.token_urlsafe(32)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43,}", valor)
    assert gerador.token_urlsafe(32) != valor


def test_sequencial_e_deterministico() -> None:
    a, b = SequentialTokenGenerator(), SequentialTokenGenerator()
    assert [a.token_hex(8), a.token_urlsafe(32)] == [b.token_hex(8), b.token_urlsafe(32)]
    assert re.fullmatch(r"[0-9a-f]{16}", SequentialTokenGenerator().token_hex(8))
