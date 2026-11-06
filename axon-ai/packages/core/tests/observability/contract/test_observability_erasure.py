"""T103 — pseudônimo nos autores (incremento 9.7, US10; FR-031, FR-032, SC-012; research R53)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from conftest import Stores
from trace_testkit import AT

from axon_ai.observability.api import InvalidField, ObservabilityErasure, ObservabilityErasureReport, Price
from axon_ai.observability.ports import DestinationSettings
from axon_ai.observability.service import SubjectPseudonymizer

pytestmark = pytest.mark.us10

PSEUDO = "deleted:0123456789abcdef"


def _preco(model: str, autor: str) -> Price:
    return Price(
        provider="openai",
        model=model,
        usd_per_mtok_in=Decimal("0.4"),
        usd_per_mtok_out=Decimal("1.6"),
        effective_from=date(2026, 10, 1),
        created_by=autor,
        created_at=AT,
    )


async def _cenario(stores: Stores) -> ObservabilityErasure:
    for model, autor in (("a", "user:ana"), ("b", "user:ana"), ("c", "user:bia")):
        await stores.prices.add(_preco(model, autor))
    await stores.settings.put(
        DestinationSettings(capture_content=False, version=1, updated_by="user:ana", updated_at=AT), expected_version=0
    )
    return SubjectPseudonymizer(prices=stores.prices, settings=stores.settings)


async def test_cenarios_1_e_2(stores: Stores) -> None:
    erasure = await _cenario(stores)

    report = await erasure.erase_subject("user:ana", pseudonym=PSEUDO)

    assert report == ObservabilityErasureReport(prices=2, destination_settings=1)
    assert sorted(p.created_by for p in await stores.prices.all()) == [PSEUDO, PSEUDO, "user:bia"]
    ajustes = await stores.settings.get()
    assert (ajustes.updated_by, ajustes.version) == (PSEUDO, 1)
    assert await erasure.erase_subject("user:ana", pseudonym=PSEUDO) == ObservabilityErasureReport()


@pytest.mark.parametrize(
    ("subject", "pseudonym", "field"),
    [
        ("", PSEUDO, "subject"),
        ("cli", PSEUDO, "subject"),
        (PSEUDO, "deleted:fedcba9876543210", "subject"),
        ("user:ana", "deleted:XYZ", "pseudonym"),
        ("user:ana", "user:outra", "pseudonym"),
    ],
)
async def test_cenario_3_formatos_recusados_sem_tocar_os_dados(
    stores: Stores, subject: str, pseudonym: str, field: str
) -> None:
    erasure = await _cenario(stores)
    precos, ajustes = await stores.prices.all(), await stores.settings.get()

    with pytest.raises(InvalidField) as erro:
        await erasure.erase_subject(subject, pseudonym=pseudonym)

    assert erro.value.field == field
    assert (await stores.prices.all(), await stores.settings.get()) == (precos, ajustes)


async def test_sc_012_nenhuma_linha_do_schema_cita_o_subject(migrated_pool: Any) -> None:
    from axon_ai.observability.adapters import postgres

    stores = Stores(
        usage=postgres.PostgresUsageStore(migrated_pool),
        prices=postgres.PostgresPriceStore(migrated_pool),
        settings=postgres.PostgresDestinationSettingsStore(migrated_pool),
    )
    erasure = await _cenario(stores)
    await erasure.erase_subject("user:ana", pseudonym=PSEUDO)

    async with migrated_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'observability' "
            "AND data_type IN ('text', 'jsonb', 'ARRAY')"
        )
        columns = await cursor.fetchall()
        achados = []
        for table, column in columns:
            cursor = await connection.execute(
                f"SELECT count(*) FROM observability.{table} WHERE {column}::text LIKE %s", ("%user:ana%",)
            )
            (count,) = await cursor.fetchone()
            if count:
                achados.append((table, column, count))
    assert columns and achados == []
    assert len(await stores.prices.all()) == 3
