"""T084 — consulta de uso e preços na administração: padrões, fuso e dinheiro como string decimal (R44)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from axon_ai.http.domain.admin_common import AdminInvalid
from axon_ai.http.domain.admin_usage import period_params, price_body, usage_query

pytestmark = pytest.mark.us9

NOW = datetime(2026, 10, 14, 2, 30, tzinfo=UTC)


def test_padroes_no_fuso_da_instalacao() -> None:
    query = usage_query({}, now=NOW, default_tz="America/Sao_Paulo")
    # 02:30 em UTC ainda é dia 13 em São Paulo: os últimos 30 dias terminam no dia local.
    assert (query.start, query.end) == (date(2026, 9, 14), date(2026, 10, 13))
    assert (query.tz, query.by, query.origin) == ("America/Sao_Paulo", "model", "production")


def test_parametros_explicitos() -> None:
    query = usage_query(
        {"from": "2026-10-01", "to": "2026-10-07", "tz": "UTC", "by": "assistant", "origin": "all"},
        now=NOW,
        default_tz="America/Sao_Paulo",
    )
    assert (query.start, query.end, query.by, query.origin) == (
        date(2026, 10, 1),
        date(2026, 10, 7),
        "assistant",
        "all",
    )


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"from": "ontem"}, "from"),
        ({"tz": "Lua/Base"}, "tz"),
        ({"by": "dia"}, "by"),
        ({"origin": "teste"}, "origin"),
        ({"from": "2026-10-07", "to": "2026-10-01"}, "from"),
        ({"pagina": "2"}, "pagina"),
    ],
)
def test_consulta_invalida_nomeia_o_parametro(params: dict[str, str], field: str) -> None:
    with pytest.raises(AdminInvalid) as caught:
        usage_query(params, now=NOW, default_tz="UTC")
    assert caught.value.field == field


def test_preco_em_string_decimal() -> None:
    fields = price_body(
        {"provider": "ollama", "model": "qwen3:1.7b", "input": "0.15", "output": "0", "effective_from": "2026-09-14"}
    )
    assert fields["usd_per_mtok_in"] == Decimal("0.15") and fields["effective_from"] == date(2026, 9, 14)
    for body, field in (
        ({"provider": "p", "model": "m", "input": 0.15, "output": "0", "effective_from": "2026-09-14"}, "input"),
        ({"provider": "p", "model": "m", "input": "x", "output": "0", "effective_from": "2026-09-14"}, "input"),
        ({"provider": "p", "model": "m", "input": "1", "output": "0", "effective_from": "14/09"}, "effective_from"),
        ({"provider": "p", "model": "m", "input": "1", "output": "0"}, "effective_from"),
    ):
        with pytest.raises(AdminInvalid) as caught:
            price_body(body)
        assert caught.value.field == field


def test_periodo_dos_modelos_sem_preco() -> None:
    assert period_params({"from": "2026-10-01", "to": "2026-10-02"}, now=NOW, default_tz="UTC") == (
        date(2026, 10, 1),
        date(2026, 10, 2),
    )
    with pytest.raises(AdminInvalid):
        period_params({"by": "model"}, now=NOW, default_tz="UTC")
