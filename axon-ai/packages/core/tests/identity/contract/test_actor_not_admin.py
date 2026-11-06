"""T098 — US11: o ator que não administra (ADR-057, item 4; research R31; SC-010 adversarial). Memória e Postgres."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from identity_testkit import ADMIN_GROUP, T0, Harness, harness

from axon_ai.identity.api import AccountDraft, AccountPatch, ActorNotAllowed, IssuedPassword

pytestmark = pytest.mark.us11

PROV = "svc:provisionamento"


async def _env(stores: Any) -> Harness:
    parts = harness(stores=stores)
    await parts.service.start()
    await parts.accounts.add_group("equipe", at=T0)
    await parts.add_account("root", groups={ADMIN_GROUP})
    await parts.add_account("chefe", groups={ADMIN_GROUP, "equipe"})
    await parts.add_account("ana", groups={"equipe"})
    return parts


def _cases(parts: Harness) -> list[tuple[str, str, Callable[[], Awaitable[object]]]]:
    service = parts.service
    no = {"actor": PROV, "actor_can_admin": False}

    async def update_admin() -> object:
        chefe = await service.account("chefe")
        return await service.update("chefe", AccountPatch(name="Chefe X"), version=chefe.version, **no)  # type: ignore[arg-type]

    async def promote() -> object:
        ana = await service.account("ana")
        patch = AccountPatch(groups=frozenset({ADMIN_GROUP, "equipe"}))
        return await service.update("ana", patch, version=ana.version, **no)  # type: ignore[arg-type]

    draft = AccountDraft(username="eva", email="eva@exemplo.org", name="Eva", groups=frozenset({ADMIN_GROUP}))
    return [
        ("cadastrar no grupo de administração", "groups", lambda: service.create(draft, **no)),  # type: ignore[arg-type]
        ("alterar conta de admin", "username", update_admin),
        ("promover pelos grupos", "groups", promote),
        ("redefinir senha de admin", "username", lambda: service.reset_password("chefe", **no)),  # type: ignore[arg-type]
        ("desativar admin", "username", lambda: service.disable("chefe", **no)),  # type: ignore[arg-type]
        ("reativar admin", "username", lambda: service.enable("chefe", **no)),  # type: ignore[arg-type]
        ("desfazer Google de admin", "username", lambda: service.unlink_google("chefe", **no)),  # type: ignore[arg-type]
        ("apagar admin", "username", lambda: service.delete("chefe", **no)),  # type: ignore[arg-type]
        ("pôr no grupo de administração", "group", lambda: service.add_group("ana", ADMIN_GROUP, **no)),  # type: ignore[arg-type]
        ("tirar do grupo de administração", "group", lambda: service.remove_group("chefe", ADMIN_GROUP, **no)),  # type: ignore[arg-type]
        ("tirar admin de grupo comum", "username", lambda: service.remove_group("chefe", "equipe", **no)),  # type: ignore[arg-type]
        (
            "membros do grupo de administração",
            "name",
            lambda: service.set_members(ADMIN_GROUP, frozenset({"root"}), **no),
        ),  # type: ignore[arg-type]
        ("tirar admin pelos membros", "members", lambda: service.set_members("equipe", frozenset({"ana"}), **no)),  # type: ignore[arg-type]
        (
            "pôr admin pelos membros",
            "members",
            lambda: service.set_members("equipe", frozenset({"ana", "chefe", "root"}), **no),
        ),  # type: ignore[arg-type]
    ]


async def test_cada_recusa_nomeia_o_campo_e_nao_muda_nada(stores: Any) -> None:
    parts = await _env(stores)
    antes = {item.username: item for item in (await parts.service.accounts(active=None)).items}
    for nome, campo, call in _cases(parts):
        with pytest.raises(ActorNotAllowed) as error:
            await call()
        assert error.value.field == campo, nome
    depois = {item.username: item for item in (await parts.service.accounts(active=None)).items}
    assert depois == antes


async def test_contas_e_grupos_comuns_seguem_valendo(stores: Any) -> None:
    parts = await _env(stores)
    service = parts.service
    criada = await service.create(
        AccountDraft(username="eva", email="eva@exemplo.org", name="Eva", groups=frozenset({"equipe"})),
        actor=PROV,
        actor_can_admin=False,
    )
    assert isinstance(criada, IssuedPassword)
    await service.create_group("vendas", actor=PROV)
    await service.add_group("eva", "vendas", actor=PROV, actor_can_admin=False)
    await service.remove_group("eva", "equipe", actor=PROV, actor_can_admin=False)
    await service.set_members("vendas", frozenset({"eva", "ana"}), actor=PROV, actor_can_admin=False)
    await service.disable("eva", actor=PROV, actor_can_admin=False)
    await service.enable("eva", actor=PROV, actor_can_admin=False)
    await service.reset_password("eva", actor=PROV, actor_can_admin=False)
    assert (await service.delete("eva", actor=PROV, actor_can_admin=False)).complete
    await service.delete_group("vendas", actor=PROV, actor_can_admin=False)
    # leituras: tudo, inclusive o grupo de administração e os membros dele
    assert {g.name for g in await service.groups()} >= {ADMIN_GROUP, "equipe"}
    assert (await service.account("chefe")).groups == frozenset({ADMIN_GROUP, "equipe"})


async def test_sem_o_parametro_vale_como_antes(stores: Any) -> None:
    parts = await _env(stores)
    await parts.service.add_group("ana", ADMIN_GROUP, actor="user:root")
    assert ADMIN_GROUP in (await parts.service.account("ana")).groups
