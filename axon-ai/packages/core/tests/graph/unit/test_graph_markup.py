"""Filtro da marcação de chamada de tool no texto da geração (research R50)."""

from __future__ import annotations

import pytest

from axon_ai.graph.domain.markup import ToolMarkupFilter


def _run(pieces: list[str]) -> tuple[str, int]:
    markup = ToolMarkupFilter()
    out = "".join(markup.feed(piece) for piece in pieces) + markup.finish()
    return out, markup.removed


def test_texto_sem_marca_passa_inteiro() -> None:
    assert _run(["Olá, ", "tudo bem? 3 < 4"]) == ("Olá, tudo bem? 3 < 4", 0)


def test_bloco_inteiro_sai() -> None:
    text = "Antes <tool_call>mango.grafico<arg_key>tipo</arg_key><arg_value>x</arg_value></tool_call> depois"
    assert _run([text]) == ("Antes  depois", 1)


@pytest.mark.parametrize("size", [1, 2, 3, 5, 7])
def test_marca_partida_entre_pedacos(size: int) -> None:
    text = "a<tool_call>x</tool_call>b<tool_call>y</tool_call>c"
    pieces = [text[i : i + size] for i in range(0, len(text), size)]
    assert _run(pieces) == ("abc", 2)


def test_bloco_sem_fechamento_descarta_o_resto() -> None:
    assert _run(["ok <tool_call>mango.grafico<arg_key>tipo"]) == ("ok ", 1)


def test_comeco_de_marca_que_nao_se_completa_sai_no_fim() -> None:
    assert _run(["valor <tool_"]) == ("valor <tool_", 0)
