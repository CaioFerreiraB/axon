"""Blocos ```axon-chart da geração: filtro em streaming e leitura do JSON (ADR-054; research R56). Puro."""

from __future__ import annotations

import json

import pytest

from axon_ai.graph.domain.chart_blocks import OPEN, ChartBlockFilter, parse_chart

ROSCA = {
    "kind": "donut",
    "title": "Gastos",
    "unit": "R$",
    "unit_position": "prefix",
    "series": [{"name": "Gastos", "points": [{"x": "A", "y": 2}, {"x": "B", "y": 3}]}],
}


def bloco(value: object) -> str:
    return f"{OPEN}\n{json.dumps(value)}\n```"


def alimentar(texto: str, tamanho: int) -> tuple[str, list[str]]:
    filtro = ChartBlockFilter()
    saida = "".join(filtro.feed(texto[i : i + tamanho]) for i in range(0, len(texto), tamanho)) + filtro.finish()
    return saida, filtro.blocks


@pytest.mark.parametrize("tamanho", [1, 2, 3, 7, 1000])
def test_o_bloco_sai_do_texto_em_qualquer_corte_do_streaming(tamanho: int) -> None:
    texto = f"Aqui está.\n\n{bloco(ROSCA)}\n\nA maior fatia é B."
    saida, blocos = alimentar(texto, tamanho)
    assert saida == "Aqui está.\n\n\n\nA maior fatia é B."
    assert len(blocos) == 1 and json.loads(blocos[0]) == ROSCA


def test_outros_blocos_de_codigo_passam_inteiros() -> None:
    texto = "Exemplo:\n```python\nprint(1)\n```\nfim"
    assert alimentar(texto, 2) == (texto, [])


def test_bloco_sem_fechar_conta_no_fim() -> None:
    saida, blocos = alimentar(f"Pronto.\n{OPEN}\n{json.dumps(ROSCA)}", 5)
    assert saida == "Pronto.\n" and json.loads(blocos[0]) == ROSCA


def test_le_o_chart_com_pontos_em_objeto_ou_par_e_infere_o_eixo() -> None:
    chart = parse_chart(json.dumps(ROSCA))
    assert (chart.kind, chart.unit, chart.unit_position, chart.x_type) == ("donut", "R$", "prefix", "nominal")
    linha = {
        "kind": "line",
        "title": "Saldo",
        "series": [{"name": "s", "points": [["2026-09-01", 10], ["2026-10-01", 12]]}],
    }
    assert parse_chart(json.dumps(linha)).x_type == "temporal"


@pytest.mark.parametrize(
    ("source", "fragmento"),
    [
        ("{nada", "JSON inválido"),
        ("[1, 2]", "objeto JSON"),
        (json.dumps(ROSCA | {"kind": "radar"}), "kind"),
        (json.dumps(ROSCA | {"series": "x"}), "lista"),
        (json.dumps(ROSCA | {"series": [{"name": "s", "points": [{"x": "a", "y": -1}]}]}), "negativo"),
    ],
)
def test_erro_legivel(source: str, fragmento: str) -> None:
    with pytest.raises(ValueError, match=fragmento):
        parse_chart(source)
