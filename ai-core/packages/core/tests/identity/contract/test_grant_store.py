"""T011/T065 — conformidade do `GrantStore` (memória e Postgres): uso único do código, rotação atômica, revogação
em cascata e expurgo (FR-006, FR-007, FR-014)."""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import timedelta
from typing import Any

from identity_testkit import T0, account

from ai_core.identity.ports import AuthorizationCode, PendingAuthorization, RefreshToken, Session


def _pending(id_hash: str = "p1", **changes: Any) -> PendingAuthorization:
    base = PendingAuthorization(
        id_hash=id_hash,
        csrf_hash="c1",
        client_id="open-webui",
        redirect_uri="http://localhost:3000/cb",
        scope="openid",
        state="s",
        nonce="n",
        created_at=T0,
        expires_at=T0 + timedelta(minutes=10),
    )
    return dataclasses.replace(base, **changes)


def _session(id_hash: str = "s1", account_id: str = "id-ana", **changes: Any) -> Session:
    base = Session(
        id_hash=id_hash,
        account_id=account_id,
        auth_time=T0,
        amr="pwd",
        created_at=T0,
        expires_at=T0 + timedelta(days=30),
    )
    return dataclasses.replace(base, **changes)


def _code(hash: str = "k1", **changes: Any) -> AuthorizationCode:
    base = AuthorizationCode(
        hash=hash,
        client_id="open-webui",
        session_id="s1",
        account_id="id-ana",
        family_id="f1",
        redirect_uri="http://localhost:3000/cb",
        scope="openid",
        nonce="n",
        auth_time=T0,
        amr="pwd",
        expires_at=T0 + timedelta(seconds=60),
    )
    return dataclasses.replace(base, **changes)


def _refresh(hash: str = "r1", family_id: str = "f1", session_id: str = "s1", **changes: Any) -> RefreshToken:
    base = RefreshToken(
        hash=hash,
        family_id=family_id,
        session_id=session_id,
        client_id="console",
        account_id="id-ana",
        scope="openid",
        created_at=T0,
    )
    return dataclasses.replace(base, **changes)


async def _with_accounts(stores: Any) -> Any:
    await stores.accounts.insert(account("ana"))
    await stores.accounts.insert(account("bia"))
    return stores.grants


async def test_pedido_pendente_por_id_por_state_do_google_e_retirada_unica(stores: Any) -> None:
    grants = await _with_accounts(stores)
    await grants.put_pending(_pending())
    assert await grants.get_pending("p1") == _pending()
    updated = _pending(google_state_hash="g1", google_nonce="gn", google_verifier="gv", account_id="id-ana")
    await grants.replace_pending(updated)
    assert await grants.pending_by_google_state("g1") == updated
    first, second = await asyncio.gather(grants.take_pending("p1"), grants.take_pending("p1"))
    assert [first, second].count(None) == 1
    assert await grants.get_pending("p1") is None


async def test_codigo_de_uso_unico_mesmo_com_duas_trocas_concorrentes(stores: Any) -> None:
    grants = await _with_accounts(stores)
    await grants.create_session(_session())
    await grants.put_code(_code())
    at = T0 + timedelta(seconds=5)
    uses = await asyncio.gather(grants.consume_code("k1", at=at), grants.consume_code("k1", at=at))
    assert sorted(use.reused for use in uses) == [False, True]
    assert all(use.code.used_at == at for use in uses)
    assert await grants.consume_code("desconhecido", at=at) is None


async def test_rotacao_atomica_e_reuso_detectavel(stores: Any) -> None:
    grants = await _with_accounts(stores)
    await grants.create_session(_session())
    await grants.put_refresh(_refresh())
    results = await asyncio.gather(
        grants.rotate_refresh("r1", _refresh("r2")), grants.rotate_refresh("r1", _refresh("r3"))
    )
    assert sorted(results) == [False, True]
    old = await grants.get_refresh("r1")
    assert old.status == "rotated" and old.rotated_to in ("r2", "r3")
    winner = await grants.get_refresh(old.rotated_to)
    assert winner.status == "active"


async def test_revogar_familia(stores: Any) -> None:
    grants = await _with_accounts(stores)
    await grants.create_session(_session())
    await grants.put_refresh(_refresh("r1", status="rotated", rotated_to="r2"))
    await grants.put_refresh(_refresh("r2"))
    await grants.put_refresh(_refresh("x1", family_id="f2"))
    await grants.revoke_family("f1")
    assert (await grants.get_refresh("r1")).status == "revoked"
    assert (await grants.get_refresh("r2")).status == "revoked"
    assert (await grants.get_refresh("x1")).status == "active"


async def test_revogar_sessao_revoga_a_renovacao_dela(stores: Any) -> None:
    grants = await _with_accounts(stores)
    await grants.create_session(_session("s1"))
    await grants.create_session(_session("s2"))
    await grants.put_refresh(_refresh("r1", session_id="s1"))
    await grants.put_refresh(_refresh("r2", family_id="f2", session_id="s2"))
    at = T0 + timedelta(hours=1)
    await grants.revoke_session("s1", at=at)
    assert (await grants.get_session("s1")).revoked_at == at
    assert (await grants.get_refresh("r1")).status == "revoked"
    assert (await grants.get_session("s2")).revoked_at is None
    assert (await grants.get_refresh("r2")).status == "active"


async def test_revogar_sessoes_da_conta_menos_uma_e_todas(stores: Any) -> None:
    grants = await _with_accounts(stores)
    for sid, owner in (("s1", "id-ana"), ("s2", "id-ana"), ("s3", "id-bia")):
        await grants.create_session(_session(sid, owner))
        await grants.put_refresh(_refresh(f"r-{sid}", family_id=f"f-{sid}", session_id=sid, account_id=owner))
    at = T0 + timedelta(hours=1)
    await grants.revoke_account_sessions("id-ana", at=at, keep="s2")
    assert (await grants.get_session("s1")).revoked_at == at
    assert (await grants.get_session("s2")).revoked_at is None
    assert (await grants.get_session("s3")).revoked_at is None
    assert (await grants.get_refresh("r-s1")).status == "revoked"
    assert (await grants.get_refresh("r-s2")).status == "active"
    await grants.revoke_all_sessions(at=at)
    for sid in ("s2", "s3"):
        assert (await grants.get_session(sid)).revoked_at == at
        assert (await grants.get_refresh(f"r-{sid}")).status == "revoked"


async def test_expurgo(stores: Any) -> None:
    grants = await _with_accounts(stores)
    now = T0 + timedelta(days=31)
    await grants.put_pending(_pending("vencido", expires_at=now - timedelta(seconds=1)))
    await grants.put_pending(_pending("vivo", expires_at=now + timedelta(minutes=5)))
    await grants.create_session(_session("s-vencida"))
    await grants.create_session(_session("s-viva", expires_at=now + timedelta(days=1)))
    await grants.create_session(_session("s-revogada", expires_at=now + timedelta(days=1), revoked_at=now))
    await grants.put_refresh(_refresh("r-vencida", session_id="s-vencida"))
    await grants.put_refresh(_refresh("r-viva", family_id="f2", session_id="s-viva"))
    await grants.put_code(_code("velho", expires_at=now - timedelta(hours=2)))
    await grants.put_code(_code("recente", expires_at=now - timedelta(minutes=5)))
    removed = await grants.purge(now=now, codes_before=now - timedelta(hours=1))
    assert removed == 5  # pedido vencido, duas sessões, a renovação de uma delas e o código velho
    assert await grants.get_pending("vencido") is None and await grants.get_pending("vivo") is not None
    assert await grants.get_session("s-vencida") is None and await grants.get_session("s-revogada") is None
    assert await grants.get_session("s-viva") is not None
    assert await grants.get_refresh("r-vencida") is None and await grants.get_refresh("r-viva") is not None
    assert await grants.consume_code("velho", at=now) is None
    assert await grants.consume_code("recente", at=now) is not None
