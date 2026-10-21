"""Contraste AA dos tokens das páginas nos dois temas (US8 cenário 4; FR-023; research R22), inclusive o hover do botão
primário, que no escuro escurece para `#1D4ED8` (ADR-039, decidido na passada da 013 para os dois CSS).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from axon_ai.identity.adapters import http

pytestmark = pytest.mark.us8

CSS = http.STYLESHEET.read_text(encoding="utf-8")
TEXT_PAIRS = [
    ("texto-primario", "fundo-base"),
    ("texto-primario", "fundo-sutil"),
    ("texto-secundario", "fundo-base"),
    ("texto-secundario", "fundo-sutil"),
    ("texto-terciario", "fundo-base"),
    ("texto-terciario", "fundo-sutil"),
    ("acao-texto", "fundo-base"),
    ("texto-sobre-acao", "acao-base"),
    ("texto-sobre-acao", "acao-hover"),
    ("ok-texto", "ok-fundo"),
    ("erro-texto", "erro-fundo"),
    ("foco", "fundo-base"),
    ("foco", "fundo-sutil"),
]


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block))


def _themes() -> dict[str, dict[str, str]]:
    light = _tokens(CSS.split("@media (prefers-color-scheme: dark)")[0])
    dark_block = re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([^}]*)\}", CSS)
    assert dark_block is not None
    return {"claro": light, "escuro": light | _tokens(dark_block.group(1))}


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("theme", ["claro", "escuro"])
@pytest.mark.parametrize(("text", "ground"), TEXT_PAIRS)
def test_pares_de_texto_atendem_aa(theme: str, text: str, ground: str) -> None:
    tokens = _themes()[theme]
    assert _ratio(tokens[text], tokens[ground]) >= 4.5, (theme, text, ground)


def test_o_fundo_escuro_e_o_axon_night() -> None:
    assert _themes()["escuro"]["fundo-base"].lower() == "#0b0f19"
    assert Path(http.STYLESHEET).name == "identity.css"
