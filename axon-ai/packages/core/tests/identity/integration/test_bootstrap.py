"""T032 — admin inicial pelas variáveis da instalação, só com zero contas (FR-018)."""

from __future__ import annotations

import logging

import pytest
from identity_testkit import ADMIN_GROUP, harness

from axon_ai.identity.ports import BootstrapAdmin

ADMIN = BootstrapAdmin(username="admin", email="admin@exemplo.org", password="senha-do-admin-inicial")


async def test_sem_contas_cria_o_admin_com_a_senha_do_arquivo() -> None:
    parts = harness(bootstrap=ADMIN)
    await parts.service.start()
    account = await parts.service.bootstrap_admin()
    assert account is not None
    assert account.username == "admin" and account.groups == frozenset({ADMIN_GROUP})
    assert not account.temporary_password and account.updated_by == "bootstrap"
    record = await parts.accounts.by_username("admin")
    assert await parts.hasher.verify(record.password_hash, "senha-do-admin-inicial")


async def test_com_contas_as_variaveis_sao_ignoradas_com_aviso(caplog: pytest.LogCaptureFixture) -> None:
    parts = harness(bootstrap=ADMIN)
    await parts.service.start()
    await parts.add_account("ana")
    with caplog.at_level(logging.WARNING, logger="axon_ai.identity"):
        assert await parts.service.bootstrap_admin() is None
    assert "bootstrap.ignored" in caplog.text
    assert await parts.accounts.by_username("admin") is None
    assert "senha-do-admin-inicial" not in caplog.text


async def test_sem_variaveis_nada_acontece() -> None:
    parts = harness()
    await parts.service.start()
    assert await parts.service.bootstrap_admin() is None
    assert await parts.accounts.count() == 0
