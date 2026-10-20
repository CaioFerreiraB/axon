"""T011 — conformidade do `AccountStore` (memória e Postgres): unicidade, versão, grupos e membros (FR-001, FR-012)."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from typing import Any

import pytest
from identity_testkit import T0, account

from axon_ai.identity.api import Conflict, GroupNotFound
from axon_ai.identity.ports import AccountRecord


def _bumped(record: AccountRecord, **changes: Any) -> AccountRecord:
    account_obj = dataclasses.replace(record.account, version=record.account.version + 1, **changes)
    return dataclasses.replace(record, account=account_obj)


async def test_insere_e_busca_por_id_usuario_email_e_google(stores: Any) -> None:
    store = stores.accounts
    await store.add_group("equipe", at=T0)
    record = account("ana", groups={"equipe"}, google_sub="google-1")
    await store.insert(record)
    assert await store.get("id-ana") == record
    assert await store.by_username("ana") == record
    assert await store.by_username("ANA") == record
    assert await store.by_email("Ana@Exemplo.org") == record
    assert await store.by_google_sub("google-1") == record
    assert await store.by_username("bia") is None
    assert await store.count() == 1


@pytest.mark.parametrize(
    ("other", "field"),
    [
        (account("ana", account_id="id-2", email="outra@exemplo.org"), "username"),
        (account("bia", email="ana@exemplo.org"), "email"),
        (account("bia", google_sub="google-1"), "google_sub"),
    ],
)
async def test_unicidade_inclusive_com_conta_desativada(stores: Any, other: AccountRecord, field: str) -> None:
    store = stores.accounts
    await store.insert(account("ana", active=False, google_sub="google-1"))
    with pytest.raises(Conflict) as caught:
        await store.insert(other)
    assert caught.value.field == field


async def test_grupo_inexistente_na_insercao(stores: Any) -> None:
    with pytest.raises(GroupNotFound):
        await stores.accounts.insert(account("ana", groups={"fantasma"}))


async def test_replace_com_versao_certa_grava_e_com_versao_velha_e_conflito(stores: Any) -> None:
    store = stores.accounts
    await store.add_group("equipe", at=T0)
    record = account("ana")
    await store.insert(record)
    updated = _bumped(record, name="Ana Souza", groups=frozenset({"equipe"}), active=False)
    await store.replace(updated, expected_version=1)
    assert await store.get("id-ana") == updated
    with pytest.raises(Conflict) as caught:
        await store.replace(_bumped(record, name="De novo"), expected_version=1)
    assert caught.value.field == "version"
    assert caught.value.current_version == 2


async def test_replace_nao_toma_email_de_outra_conta(stores: Any) -> None:
    store = stores.accounts
    await store.insert(account("ana"))
    bia = account("bia")
    await store.insert(bia)
    with pytest.raises(Conflict) as caught:
        await store.replace(_bumped(bia, email="ana@exemplo.org"), expected_version=1)
    assert caught.value.field == "email"


async def test_lista_ordenada_com_busca_filtro_e_cursor(stores: Any) -> None:
    store = stores.accounts
    for name in ("carla", "ana", "bia", "beto"):
        await store.insert(account(name, active=name != "beto", name=f"Pessoa {name.upper()}"))
    page = await store.list(query=None, active=None, limit=10, after=None)
    assert [r.account.username for r in page] == ["ana", "beto", "bia", "carla"]
    page = await store.list(query=None, active=True, limit=2, after=None)
    assert [r.account.username for r in page] == ["ana", "bia"]
    page = await store.list(query=None, active=True, limit=2, after="bia")
    assert [r.account.username for r in page] == ["carla"]
    page = await store.list(query="pessoa b", active=None, limit=10, after=None)
    assert [r.account.username for r in page] == ["beto", "bia"]
    page = await store.list(query="_", active=None, limit=10, after=None)
    assert page == ()


async def test_grupos_contam_so_membros_ativos(stores: Any) -> None:
    store = stores.accounts
    await store.add_group("equipe", at=T0)
    await store.add_group("vazio", at=T0)
    await store.insert(account("ana", groups={"equipe"}))
    await store.insert(account("bia", groups={"equipe"}, active=False))
    assert await store.groups() == {"equipe": 1, "vazio": 0}
    assert await store.active_members("equipe") == frozenset({"id-ana"})
    with pytest.raises(Conflict) as caught:
        await store.add_group("equipe", at=T0)
    assert caught.value.field == "name"


async def test_apagar_grupo_remove_associacoes_e_sobe_versao(stores: Any) -> None:
    store = stores.accounts
    await store.add_group("equipe", at=T0)
    await store.insert(account("ana", groups={"equipe"}))
    await store.insert(account("bia"))
    later = T0 + timedelta(minutes=1)
    assert await store.remove_group("equipe", at=later, actor="user:admin") is True
    ana = await store.get("id-ana")
    assert ana.account.groups == frozenset()
    assert ana.account.version == 2 and ana.account.updated_by == "user:admin" and ana.account.updated_at == later
    assert (await store.get("id-bia")).account.version == 1
    assert await store.remove_group("equipe", at=later, actor="user:admin") is False
    assert "equipe" not in await store.groups()


async def test_definir_membros_so_mexe_em_quem_mudou(stores: Any) -> None:
    store = stores.accounts
    await store.add_group("equipe", at=T0)
    await store.insert(account("ana", groups={"equipe"}))
    await store.insert(account("bia", groups={"equipe"}))
    await store.insert(account("carla"))
    later = T0 + timedelta(minutes=1)
    await store.set_members("equipe", ["id-bia", "id-carla"], at=later, actor="cli")
    assert (await store.get("id-ana")).account.groups == frozenset()
    assert (await store.get("id-ana")).account.version == 2
    assert (await store.get("id-bia")).account.version == 1
    carla = (await store.get("id-carla")).account
    assert carla.groups == frozenset({"equipe"}) and carla.version == 2
    with pytest.raises(GroupNotFound):
        await store.set_members("fantasma", [], at=later, actor="cli")
