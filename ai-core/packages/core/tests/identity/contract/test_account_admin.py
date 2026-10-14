"""T031 — conformidade do seam `AccountAdmin` (memória e Postgres; FR-001, FR-002, FR-010 a FR-012, FR-015)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from identity_testkit import ADMIN_GROUP, Harness

from ai_core.identity.api import (
    Account,
    AccountDraft,
    AccountNotFound,
    AccountPatch,
    Conflict,
    GroupNotFound,
    InvalidField,
    IssuedPassword,
    ProtectedGroup,
)
from ai_core.identity.domain.accounts import TEMPORARY_PASSWORD_PATTERN
from ai_core.identity.ports import Session

ACTOR = "user:root"


def _draft(username: str = "ana", **changes: object) -> AccountDraft:
    values: dict[str, object] = {"username": username, "email": f"{username}@exemplo.org", "name": username.title()}
    values.update(changes)
    return AccountDraft(**values)  # type: ignore[arg-type]


async def _admin(seam: Harness, username: str = "root") -> Account:
    created = await seam.service.create(_draft(username, groups=frozenset({ADMIN_GROUP})), actor="cli")
    assert isinstance(created, IssuedPassword)
    return created.account


async def test_cadastro_gera_senha_temporaria_uma_vez(seam: Harness) -> None:
    await seam.service.create_group("equipe", actor=ACTOR)
    issued = await seam.service.create(_draft(groups=frozenset({"equipe"})), actor=ACTOR)
    assert isinstance(issued, IssuedPassword)
    assert TEMPORARY_PASSWORD_PATTERN.fullmatch(issued.temporary_password)
    assert issued.temporary_password not in repr(issued)
    account = issued.account
    assert account.temporary_password and account.has_password and account.active and not account.google_linked
    assert account.groups == frozenset({"equipe"}) and account.updated_by == ACTOR and account.version == 1
    assert await seam.service.account("ana") == account
    record = await seam.accounts.by_username("ana")
    assert await seam.hasher.verify(record.password_hash, issued.temporary_password)
    # a senha temporária não volta por nenhuma leitura
    listed = await seam.service.accounts()
    assert issued.temporary_password not in repr(listed)


async def test_cadastro_so_google_sem_senha(seam: Harness) -> None:
    account = await seam.service.create(_draft(google_only=True), actor=ACTOR)
    assert isinstance(account, Account)
    assert not account.has_password and not account.temporary_password


@pytest.mark.parametrize(
    ("draft", "field"),
    [
        (_draft("ana", email="outra@exemplo.org"), "username"),
        (_draft("bia", email="ana@exemplo.org"), "email"),
    ],
)
async def test_nome_e_email_livres_entre_todas_inclusive_desativadas(
    seam: Harness, draft: AccountDraft, field: str
) -> None:
    await _admin(seam)
    await seam.service.create(_draft("ana"), actor=ACTOR)
    await seam.service.disable("ana", actor=ACTOR)
    with pytest.raises(Conflict) as caught:
        await seam.service.create(draft, actor=ACTOR)
    assert caught.value.field == field


async def test_grupo_inexistente_no_cadastro(seam: Harness) -> None:
    with pytest.raises(InvalidField) as caught:
        await seam.service.create(_draft(groups=frozenset({"fantasma"})), actor=ACTOR)
    assert caught.value.field == "groups"


async def test_alteracao_com_versao_e_autor(seam: Harness) -> None:
    await seam.service.create_group("equipe", actor=ACTOR)
    created = await seam.service.create(_draft(), actor=ACTOR)
    assert isinstance(created, IssuedPassword)
    seam.clock.advance(timedelta(minutes=1))
    updated = await seam.service.update(
        "ana",
        AccountPatch(email="ana.souza@exemplo.org", name="Ana Souza", groups=frozenset({"equipe"})),
        actor="user:bia",
        version=1,
    )
    assert (updated.email, updated.name, updated.groups) == (
        "ana.souza@exemplo.org",
        "Ana Souza",
        frozenset({"equipe"}),
    )
    assert updated.version == 2 and updated.updated_by == "user:bia" and updated.updated_at == seam.clock.now()
    with pytest.raises(Conflict) as caught:
        await seam.service.update("ana", AccountPatch(name="De novo"), actor=ACTOR, version=1)
    assert caught.value.field == "version" and caught.value.current_version == 2


async def test_trocar_email_mantem_o_vinculo_google(seam: Harness) -> None:
    await seam.add_account("ana", google_sub="google-ana")
    updated = await seam.service.update("ana", AccountPatch(email="nova@exemplo.org"), actor=ACTOR, version=1)
    assert updated.google_linked
    assert (await seam.accounts.by_google_sub("google-ana")).account.email == "nova@exemplo.org"
    unlinked = await seam.service.unlink_google("ana", actor=ACTOR)
    assert not unlinked.google_linked and await seam.accounts.by_google_sub("google-ana") is None


async def test_conta_inexistente(seam: Harness) -> None:
    for call in (
        seam.service.account("zeca"),
        seam.service.disable("zeca", actor=ACTOR),
        seam.service.reset_password("zeca", actor=ACTOR),
    ):
        with pytest.raises(AccountNotFound):
            await call


async def test_grupo_de_administracao_protegido(seam: Harness) -> None:
    root = await _admin(seam)
    groups = {group.name: group for group in await seam.service.groups()}
    assert groups[ADMIN_GROUP].protected and groups[ADMIN_GROUP].members == 1
    with pytest.raises(ProtectedGroup):
        await seam.service.delete_group(ADMIN_GROUP, actor=ACTOR)
    with pytest.raises(ProtectedGroup):
        await seam.service.disable("root", actor=ACTOR)
    with pytest.raises(ProtectedGroup):
        await seam.service.update("root", AccountPatch(groups=frozenset()), actor=ACTOR, version=root.version)
    with pytest.raises(ProtectedGroup):
        await seam.service.set_members(ADMIN_GROUP, frozenset(), actor=ACTOR)
    # com outro admin ativo, o primeiro pode sair
    await _admin(seam, "bia")
    assert (await seam.service.disable("root", actor=ACTOR)).active is False
    with pytest.raises(ProtectedGroup):
        await seam.service.set_members(ADMIN_GROUP, frozenset({"root"}), actor=ACTOR)  # root desativado não conta


async def test_grupos_membros_e_apagar(seam: Harness) -> None:
    await seam.service.create(_draft("ana"), actor=ACTOR)
    await seam.service.create(_draft("bia"), actor=ACTOR)
    group = await seam.service.create_group("equipe", actor=ACTOR)
    assert group.members == 0 and not group.protected
    with pytest.raises(Conflict):
        await seam.service.create_group("equipe", actor=ACTOR)
    with pytest.raises(InvalidField):
        await seam.service.create_group("Equipe Azul", actor=ACTOR)
    group = await seam.service.set_members("equipe", frozenset({"ana", "bia"}), actor=ACTOR)
    assert group.members == 2
    assert (await seam.service.account("ana")).groups == frozenset({"equipe"})
    with pytest.raises(InvalidField):
        await seam.service.set_members("equipe", frozenset({"zeca"}), actor=ACTOR)
    with pytest.raises(GroupNotFound):
        await seam.service.set_members("fantasma", frozenset(), actor=ACTOR)
    await seam.service.delete_group("equipe", actor=ACTOR)
    ana = await seam.service.account("ana")
    assert ana.groups == frozenset() and ana.updated_by == ACTOR
    with pytest.raises(GroupNotFound):
        await seam.service.delete_group("equipe", actor=ACTOR)


async def _session_for(seam: Harness, username: str, sid: str) -> None:
    account = await seam.service.account(username)
    now = seam.clock.now()
    await seam.grants.create_session(
        Session(
            id_hash=sid,
            account_id=account.id,
            auth_time=now,
            amr="pwd",
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
    )


async def test_desativar_e_redefinir_senha_encerram_as_sessoes(seam: Harness) -> None:
    await seam.service.create(_draft("ana"), actor=ACTOR)
    await _session_for(seam, "ana", "s1")
    await seam.service.disable("ana", actor=ACTOR)
    assert (await seam.grants.get_session("s1")).revoked_at is not None
    enabled = await seam.service.enable("ana", actor=ACTOR)
    assert enabled.active
    await _session_for(seam, "ana", "s2")
    issued = await seam.service.reset_password("ana", actor=ACTOR)
    assert issued.account.temporary_password and TEMPORARY_PASSWORD_PATTERN.fullmatch(issued.temporary_password)
    assert (await seam.grants.get_session("s2")).revoked_at is not None


async def test_listagem_paginada_e_filtrada(seam: Harness) -> None:
    for name in ("ana", "bia", "carla"):
        await seam.service.create(_draft(name), actor=ACTOR)
    await seam.service.disable("bia", actor=ACTOR)
    page = await seam.service.accounts(limit=1)
    assert [a.username for a in page.items] == ["ana"] and page.next_cursor == "ana"
    page = await seam.service.accounts(limit=1, cursor=page.next_cursor)
    assert [a.username for a in page.items] == ["carla"] and page.next_cursor is None
    everyone = await seam.service.accounts(active=None)
    assert [a.username for a in everyone.items] == ["ana", "bia", "carla"]
    assert [a.username for a in (await seam.service.accounts(query="CARLA@")).items] == ["carla"]


async def test_ator_invalido(seam: Harness) -> None:
    with pytest.raises(ValueError, match="ator"):
        await seam.service.create(_draft(), actor="alguém")
