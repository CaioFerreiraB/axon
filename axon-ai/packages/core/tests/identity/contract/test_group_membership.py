"""T096 — US10: um grupo de cada vez, sem versão (ADR-058, item 9; research R32; SC-011). Memória e Postgres."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from identity_testkit import ADMIN_GROUP, T0, Harness, harness

from axon_ai.identity.api import AccountNotFound, AccountPatch, Conflict, GroupNotFound, ProtectedGroup

pytestmark = pytest.mark.us10

ACTOR = "svc:provisionamento"


async def _env(stores: Any) -> Harness:
    parts = harness(stores=stores)
    await parts.service.start()
    await parts.accounts.add_group("equipe", at=T0)
    await parts.accounts.add_group("vendas", at=T0)
    await parts.add_account("ana")
    return parts


async def test_poe_e_tira_sem_versao_e_repetir_nao_muda_nada(stores: Any) -> None:
    parts = await _env(stores)
    antes = await parts.service.account("ana")

    depois = await parts.service.add_group("ana", "equipe", actor=ACTOR)
    assert depois.groups == frozenset({"equipe"}) and depois.version == antes.version + 1
    assert depois.updated_by == ACTOR
    assert (await parts.service.add_group("ana", "equipe", actor=ACTOR)).version == depois.version

    tirada = await parts.service.remove_group("ana", "equipe", actor=ACTOR)
    assert tirada.groups == frozenset()
    assert (await parts.service.remove_group("ana", "equipe", actor=ACTOR)).version == tirada.version


async def test_dois_grupos_ao_mesmo_tempo(stores: Any) -> None:
    parts = await _env(stores)
    await asyncio.gather(
        parts.service.add_group("ana", "equipe", actor=ACTOR), parts.service.add_group("ana", "vendas", actor=ACTOR)
    )
    assert (await parts.service.account("ana")).groups == frozenset({"equipe", "vendas"})


async def test_patch_com_versao_anterior_nao_desfaz_o_grupo(stores: Any) -> None:
    parts = await _env(stores)
    lida = await parts.service.account("ana")
    await parts.service.add_group("ana", "equipe", actor=ACTOR)
    with pytest.raises(Conflict) as error:
        await parts.service.update("ana", AccountPatch(groups=frozenset()), actor=ACTOR, version=lida.version)
    assert error.value.field == "version"


async def test_inexistentes(stores: Any) -> None:
    parts = await _env(stores)
    with pytest.raises(GroupNotFound):
        await parts.service.add_group("ana", "fantasma", actor=ACTOR)
    with pytest.raises(GroupNotFound):
        await parts.service.remove_group("ana", "fantasma", actor=ACTOR)
    with pytest.raises(AccountNotFound):
        await parts.service.add_group("ninguem", "equipe", actor=ACTOR)


async def test_ultimo_admin_nao_sai_do_grupo(stores: Any) -> None:
    parts = await _env(stores)
    await parts.add_account("root", groups={ADMIN_GROUP})
    with pytest.raises(ProtectedGroup):
        await parts.service.remove_group("root", ADMIN_GROUP, actor="user:root")
    await parts.service.add_group("ana", ADMIN_GROUP, actor="user:root")
    assert (await parts.service.remove_group("root", ADMIN_GROUP, actor="user:root")).groups == frozenset()
