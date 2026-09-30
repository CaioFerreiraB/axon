"""T023 — conformidade do seam `ApiKeyAdmin` (contracts/assistants-api.md, FR-015)."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from assistants_testkit import ANA, BIA, CAIO_KEY, CAIO_OIDC, SVC, T0, MutableClock, access_service

from ai_core.assistants.api import NotFound, Principal, RequestRejected


async def test_emissao_por_administrador_devolve_chave_que_autentica() -> None:
    service = access_service()
    issued = await service.issue(actor=CAIO_KEY, subject="svc:ingestor", groups=["leitores"], label="pipeline")

    assert issued.info.key_id == "0000000000000001"
    assert issued.plaintext == "aic_0000000000000001_segredo2"
    assert re.fullmatch(r"aic_[0-9a-f]{16}_\S+", issued.plaintext)
    assert issued.info.created_at == T0 and issued.info.active
    principal = await service.authenticate(surface="private", credential=issued.plaintext)
    assert principal == Principal(subject="svc:ingestor", scheme="api_key", groups=frozenset({"leitores"}))


async def test_grupo_com_prefixo_e_aceito() -> None:
    issued = await access_service().issue(actor=CAIO_KEY, subject="user:ana", groups=["group:chefia"])
    assert issued.info.groups == frozenset({"chefia"})


async def test_listagem_nunca_expoe_chave_nem_hash() -> None:
    service = access_service()
    issued = await service.issue(actor=CAIO_KEY, subject="user:ana")
    (info,) = await service.keys(actor=CAIO_KEY)

    assert info == issued.info
    assert not hasattr(info, "key_hash") and not hasattr(info, "plaintext")
    assert issued.plaintext not in repr(info)


async def test_revogacao_vale_na_chamada_seguinte_sem_reconstruir_o_servico() -> None:
    clock = MutableClock()
    service = access_service(clock=clock)
    issued = await service.issue(actor=CAIO_KEY, subject="user:ana")
    assert await service.authenticate(surface="private", credential=issued.plaintext) is not None

    clock.advance(30)
    revogada = await service.revoke(actor=CAIO_KEY, key_id=issued.info.key_id)
    assert revogada.revoked_at == T0 + timedelta(seconds=30)
    assert await service.authenticate(surface="private", credential=issued.plaintext) is None

    clock.advance(30)
    de_novo = await service.revoke(actor=CAIO_KEY, key_id=issued.info.key_id)
    assert de_novo.revoked_at == T0 + timedelta(seconds=30)


@pytest.mark.parametrize("actor", [ANA, BIA, CAIO_OIDC, SVC])
async def test_quem_nao_administra_recebe_not_found_nas_tres_operacoes(actor: Principal) -> None:
    service = access_service()
    existente = await service.issue(actor=CAIO_KEY, subject="user:ana")
    with pytest.raises(NotFound):
        await service.issue(actor=actor, subject="user:x")
    with pytest.raises(NotFound):
        await service.keys(actor=actor)
    with pytest.raises(NotFound):
        await service.revoke(actor=actor, key_id=existente.info.key_id)


async def test_sem_grupo_de_administracao_so_a_cli_administra() -> None:
    service = access_service(admin_group=None)
    with pytest.raises(NotFound):
        await service.keys(actor=CAIO_KEY)
    assert (await service.issue_as_operator(subject="user:ana")).plaintext


@pytest.mark.parametrize("subject", ["caio", "user:", "admin:caio", "user:com espaço"])
async def test_subject_fora_do_formato_e_recusado_nomeando_o_campo(subject: str) -> None:
    with pytest.raises(RequestRejected) as caught:
        await access_service().issue(actor=CAIO_KEY, subject=subject)
    assert caught.value.field == "subject"


async def test_revogar_chave_inexistente_e_not_found() -> None:
    with pytest.raises(NotFound):
        await access_service().revoke(actor=CAIO_KEY, key_id="00000000000000ff")
