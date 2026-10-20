"""O juiz offline: mensagens neutras, leitura da resposta e média e variância de três julgamentos (R19; T028)."""

from __future__ import annotations

import pytest

from axon_ai.eval.domain.judging import INSTRUCTION, ROUNDS, combine, messages, parse
from axon_ai.eval.ports import Judgement

pytestmark = pytest.mark.us3


def test_tres_julgamentos_media_e_variancia() -> None:
    julgado = combine(
        [
            Judgement(faithfulness=1.0, coverage=0.5),
            Judgement(faithfulness=0.5, coverage=None),
            Judgement(faithfulness=0.0, coverage=0.5),
        ]
    )
    assert ROUNDS == 3
    assert julgado.faithfulness == pytest.approx(0.5) and julgado.faithfulness_variance == pytest.approx(1 / 6)
    assert julgado.coverage == 0.5 and julgado.coverage_variance == 0.0


def test_todos_ausentes() -> None:
    julgado = combine([Judgement(faithfulness=None, coverage=None)] * 3)
    assert (julgado.faithfulness, julgado.coverage, julgado.faithfulness_variance) == (None, None, None)


@pytest.mark.parametrize(
    ("data", "esperado"),
    [
        ({"faithfulness": 0.8, "coverage": None}, (0.8, None)),
        ({"faithfulness": 1.4, "coverage": -1}, (1.0, 0.0)),
        ({"faithfulness": "alta", "coverage": True}, (None, None)),
        ("não é objeto", (None, None)),
    ],
)
def test_leitura_da_resposta(data: object, esperado: tuple[float | None, float | None]) -> None:
    julgamento = parse(data)
    assert (julgamento.faithfulness, julgamento.coverage) == esperado


def test_mensagens_cercam_os_dados_e_nao_tem_dominio() -> None:
    sistema, usuario = messages(question="Q?", answer="R.", passages=["t1", "t2"], reference=None)
    assert sistema == {"role": "system", "content": INSTRUCTION}
    assert "<trechos>\nt1\n\nt2\n</trechos>" in usuario["content"] and "(sem referência)" in usuario["content"]
    assert "escot" not in INSTRUCTION.casefold()
    assert "(nenhum trecho)" in messages(question="Q", answer="R", passages=[], reference="ref")[1]["content"]
