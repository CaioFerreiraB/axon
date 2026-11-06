"""T089 — US9: apagar uma conta em cascata (ADR-058, ADR-059; research R28 a R30; SC-009). Memória e Postgres."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from typing import Any

import pytest
from identity_testkit import ADMIN_GROUP, T0, Harness, harness

from axon_ai.identity.api import (
    AccountDraft,
    AccountNotFound,
    AccountPatch,
    Conflict,
    DeletionIncomplete,
    DeletionReport,
    InvalidField,
    ModuleErasure,
    ProtectedGroup,
)
from axon_ai.identity.domain.accounts import PSEUDONYM_PATTERN
from axon_ai.identity.ports import ErasedData, IdentitySettings, RefreshToken, Session

pytestmark = pytest.mark.us9

ACTOR = "user:root"


class Eraser:
    """Apagador de teste: registra as chamadas e falha nas primeiras `fail` vezes."""

    def __init__(self, name: str, *, fail: int = 0) -> None:
        self.name = name
        self.fail = fail
        self.calls: list[tuple[str, str, str]] = []

    async def erase(self, subject: str, *, actor: str, pseudonym: str) -> ErasedData:
        self.calls.append((subject, actor, pseudonym))
        if self.fail > 0:
            self.fail -= 1
            raise RuntimeError("banco do módulo fora do ar: senha=segredo")
        return ErasedData(counts={"itens": 2}, warnings=(f"{self.name}: aviso",))


async def _env(stores: Any, *erasers: Eraser) -> Harness:
    parts = harness(stores=stores, erasers=erasers)
    await parts.service.start()
    await parts.add_account("root", groups={ADMIN_GROUP})
    return parts


async def _ana_with_session(parts: Harness) -> None:
    await parts.add_account("ana", groups={"equipe"})
    await parts.grants.create_session(
        Session(
            id_hash="s-ana",
            account_id="id-ana",
            auth_time=T0,
            amr="pwd",
            created_at=T0,
            expires_at=T0 + timedelta(days=30),
        )
    )
    await parts.grants.put_refresh(
        RefreshToken(
            hash="r-ana",
            family_id="f-ana",
            session_id="s-ana",
            client_id="console",
            account_id="id-ana",
            scope="openid",
            created_at=T0,
        )
    )


# --- cenários 1 a 3 --------------------------------------------------------------------------------------------------


async def test_apaga_a_conta_e_o_que_ela_guarda_e_libera_o_nome(stores: Any) -> None:
    primeiro, segundo = Eraser("assistants"), Eraser("conversations")
    parts = await _env(stores, primeiro, segundo)
    await _ana_with_session(parts)

    report = await parts.service.delete("ana", actor=ACTOR)

    assert report == DeletionReport(
        username="ana",
        complete=True,
        identity={"sessions": 1, "refresh_tokens": 1, "codes": 0, "pending": 0, "authored": 0, "account": 1},
        modules=(
            ModuleErasure(name="assistants", counts={"itens": 2}, warnings=("assistants: aviso",)),
            ModuleErasure(name="conversations", counts={"itens": 2}, warnings=("conversations: aviso",)),
        ),
    )
    ((subject, actor, pseudonym),) = primeiro.calls
    assert subject == "user:ana" and actor == ACTOR and PSEUDONYM_PATTERN.fullmatch(pseudonym)
    assert segundo.calls == primeiro.calls
    assert pseudonym not in repr(report)
    assert await parts.grants.get_session("s-ana") is None and await parts.grants.get_refresh("r-ana") is None
    with pytest.raises(AccountNotFound):
        await parts.service.account("ana")
    assert (await parts.accounts.groups())["equipe"] == 0

    nova = await parts.service.create(AccountDraft(username="ana", email="ana2@exemplo.org", name="Ana"), actor=ACTOR)
    account = nova.account if hasattr(nova, "account") else nova
    assert account.groups == frozenset() and account.id != "id-ana"


async def test_autores_viram_o_pseudonimo(stores: Any) -> None:
    eraser = Eraser("assistants")
    parts = await _env(stores, eraser)
    await parts.add_account("ana")
    await parts.add_account("bia")
    bia = await parts.service.account("bia")
    await parts.service.update("bia", AccountPatch(name="Bia B"), actor="user:ana", version=bia.version)
    await parts.settings.put(
        IdentitySettings(google_enabled=False, version=1, updated_by="user:ana", updated_at=T0), expected_version=0
    )

    report = await parts.service.delete("ana", actor=ACTOR)

    ((_, _, pseudonym),) = eraser.calls
    assert report.identity["authored"] == 2
    assert (await parts.service.account("bia")).updated_by == pseudonym
    assert (await parts.settings.get()).updated_by == pseudonym


# --- cenários 4 e 5: falha e retomada --------------------------------------------------------------------------------


async def test_falha_deixa_em_apagamento_e_a_segunda_tentativa_conclui(stores: Any) -> None:
    quebra, segue = Eraser("conversations", fail=1), Eraser("mcp")
    parts = await _env(stores, quebra, segue)
    await _ana_with_session(parts)

    with pytest.raises(DeletionIncomplete) as error:
        await parts.service.delete("ana", actor=ACTOR)

    report = error.value.report
    assert not report.complete and report.identity == {}
    assert report.modules == (
        ModuleErasure(name="conversations", failed=True),
        ModuleErasure(name="mcp", counts={"itens": 2}, warnings=("mcp: aviso",)),
    )
    assert "segredo" not in str(error.value) and "segredo" not in repr(report)
    conta = (await parts.service.accounts(active=None)).items
    ana = next(item for item in conta if item.username == "ana")
    assert ana.deleting and not ana.active and ana.groups == frozenset()
    assert "ana" not in [item.username for item in (await parts.service.accounts()).items]
    assert await parts.grants.get_refresh("r-ana") is not None  # revogada, ainda não apagada
    assert (await parts.grants.get_refresh("r-ana")).status == "revoked"

    for call in (
        parts.service.enable("ana", actor=ACTOR),
        parts.service.update("ana", AccountPatch(name="X"), actor=ACTOR, version=ana.version),
        parts.service.reset_password("ana", actor=ACTOR),
        parts.service.create(AccountDraft(username="ana", email="outra@exemplo.org", name="Ana"), actor=ACTOR),
    ):
        with pytest.raises(Conflict) as conflict:
            await call
        assert conflict.value.field == "username"

    report = await parts.service.delete("ana", actor=ACTOR)

    assert report.complete
    assert quebra.calls[0][2] == quebra.calls[1][2] == segue.calls[1][2], "o mesmo pseudônimo na retomada"
    with pytest.raises(AccountNotFound):
        await parts.service.account("ana")


# --- cenários 6 e 7: recusas -----------------------------------------------------------------------------------------


async def test_propria_conta_e_ultimo_admin_sao_recusados_sem_mudar_nada(stores: Any) -> None:
    eraser = Eraser("assistants")
    parts = await _env(stores, eraser)
    await parts.add_account("ana")

    with pytest.raises(InvalidField) as error:
        await parts.service.delete("ana", actor="user:ana")
    assert error.value.field == "username"
    with pytest.raises(ProtectedGroup):
        await parts.service.delete("root", actor="user:ana")
    assert eraser.calls == []
    assert not (await parts.service.account("ana")).deleting
    assert (await parts.service.account("root")).groups == frozenset({ADMIN_GROUP})


async def test_conta_inexistente(stores: Any) -> None:
    parts = await _env(stores)
    with pytest.raises(AccountNotFound):
        await parts.service.delete("ninguem", actor=ACTOR)


async def test_admin_que_nao_e_o_ultimo_pode_ser_apagado(stores: Any) -> None:
    parts = await _env(stores)
    await parts.add_account("chefe", groups={ADMIN_GROUP})
    assert (await parts.service.delete("chefe", actor=ACTOR)).complete


async def test_conta_desativada_tambem_e_apagada(stores: Any) -> None:
    parts = await _env(stores)
    await parts.add_account("ana")
    await parts.service.disable("ana", actor=ACTOR)
    assert (await parts.service.delete("ana", actor=ACTOR)).complete


async def test_conta_em_apagamento_nao_entra_em_grupo(stores: Any) -> None:
    parts = await _env(stores, Eraser("x", fail=1))
    await parts.add_account("ana")
    await parts.accounts.add_group("vendas", at=T0)
    with pytest.raises(DeletionIncomplete):
        await parts.service.delete("ana", actor=ACTOR)
    for call in (
        parts.service.add_group("ana", "vendas", actor=ACTOR),
        parts.service.remove_group("ana", "vendas", actor=ACTOR),
    ):
        with pytest.raises(Conflict):
            await call


def test_relatorio_e_imutavel() -> None:
    report = DeletionReport(username="ana", complete=True, identity={"account": 1})
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.complete = False  # type: ignore[misc]
    with pytest.raises(TypeError):
        report.identity["account"] = 2  # type: ignore[index]
