"""T099 — US12: rotação do segredo de uma chave de API e as regras novas da emissão (ADR-040; research R38 a R40)."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from assistants_testkit import ANA, BIA, CAIO_KEY, CAIO_OIDC, SVC, T0, MutableClock, access_service

from axon_ai.assistants.api import Conflict, NotFound, Principal, RequestRejected
from axon_ai.assistants.domain.keys import hash_key

pytestmark = pytest.mark.us12


async def test_rotacao_mantem_a_chave_e_troca_o_segredo() -> None:
    clock = MutableClock()
    service = access_service(clock=clock)
    issued = await service.issue(actor=CAIO_KEY, subject="svc:relatorios", groups=["leitores"], label="prod")

    clock.advance(60)
    rotated = await service.rotate(actor=CAIO_KEY, key_id=issued.info.key_id)

    assert rotated.info.key_id == issued.info.key_id
    assert rotated.plaintext.startswith(f"axn_{issued.info.key_id}_")
    assert rotated.plaintext != issued.plaintext
    assert rotated.info.rotated_at == T0 + timedelta(seconds=60)
    for campo in ("subject", "groups", "label", "created_at", "revoked_at"):
        assert getattr(rotated.info, campo) == getattr(issued.info, campo)
    (listada,) = await service.keys(actor=CAIO_KEY)
    assert listada == rotated.info


async def test_segredo_antigo_morre_e_o_novo_autentica_com_o_mesmo_principal() -> None:
    service = access_service()
    issued = await service.issue(actor=CAIO_KEY, subject="svc:relatorios", groups=["leitores"])
    antes = await service.authenticate(surface="private", credential=issued.plaintext)

    rotated = await service.rotate(actor=CAIO_KEY, key_id=issued.info.key_id)

    assert await service.authenticate(surface="private", credential=issued.plaintext) is None
    assert await service.authenticate(surface="private", credential=rotated.plaintext) == antes


async def test_chave_de_admin_rotacionada_vale_na_administracao() -> None:
    service = access_service()
    admin = await service.issue_as_operator(subject="user:caio", groups=["operadores"])
    rotated = await service.rotate(actor=CAIO_KEY, key_id=admin.info.key_id)

    assert await service.authenticate(surface="admin", credential=admin.plaintext) is None
    principal = await service.authenticate(surface="admin", credential=rotated.plaintext)
    assert principal is not None and service.is_admin(principal)


async def test_chave_revogada_nao_rotaciona() -> None:
    service = access_service()
    issued = await service.issue(actor=CAIO_KEY, subject="svc:relatorios")
    await service.revoke(actor=CAIO_KEY, key_id=issued.info.key_id)

    with pytest.raises(Conflict, match="revogada"):
        await service.rotate(actor=CAIO_KEY, key_id=issued.info.key_id)
    (info,) = await service.keys(actor=CAIO_KEY)
    assert not info.active and info.rotated_at is None


async def test_rotacionar_inexistente_e_not_found() -> None:
    with pytest.raises(NotFound):
        await access_service().rotate(actor=CAIO_KEY, key_id="00000000000000ff")


@pytest.mark.parametrize("actor", [ANA, BIA, CAIO_OIDC, SVC])
async def test_quem_nao_administra_recebe_not_found(actor: Principal) -> None:
    service = access_service()
    issued = await service.issue(actor=CAIO_KEY, subject="svc:relatorios")
    with pytest.raises(NotFound):
        await service.rotate(actor=actor, key_id=issued.info.key_id)
    assert await service.authenticate(surface="private", credential=issued.plaintext) is not None


async def test_operador_rotaciona_pela_propria_autoridade() -> None:
    service = access_service()
    issued = await service.issue_as_operator(subject="svc:relatorios")
    rotated = await service.rotate_as_operator(key_id=issued.info.key_id)

    assert rotated.info.key_id == issued.info.key_id
    assert await service.authenticate(surface="private", credential=issued.plaintext) is None
    assert await service.authenticate(surface="private", credential=rotated.plaintext) is not None


async def test_duas_chaves_do_mesmo_sistema_sao_independentes() -> None:
    service = access_service()
    prod = await service.issue(actor=CAIO_KEY, subject="svc:relatorios", label="prod")
    homolog = await service.issue(actor=CAIO_KEY, subject="svc:relatorios", label="homolog")

    await service.rotate(actor=CAIO_KEY, key_id=prod.info.key_id)
    assert await service.authenticate(surface="private", credential=homolog.plaintext) is not None

    await service.revoke(actor=CAIO_KEY, key_id=homolog.info.key_id)
    assert await service.authenticate(surface="private", credential=homolog.plaintext) is None
    assert {info.label for info in await service.keys(actor=CAIO_KEY) if info.active} == {"prod"}


async def test_rotacionar_a_propria_chave_conclui_e_a_seguinte_e_recusada() -> None:
    service = access_service()
    propria = await service.issue_as_operator(subject="user:caio", groups=["operadores"])
    actor = await service.authenticate(surface="admin", credential=propria.plaintext)
    assert actor is not None

    rotated = await service.rotate(actor=actor, key_id=propria.info.key_id)

    assert rotated.plaintext != propria.plaintext
    assert await service.authenticate(surface="admin", credential=propria.plaintext) is None


# --- emissão: nome do sistema e grupo de administração (R40) ---------------------------------------------------------


async def test_administracao_concede_grupo_comum_e_recusa_o_de_administracao() -> None:
    service = access_service()
    comum = await service.issue(actor=CAIO_KEY, subject="svc:relatorios", groups=["equipe"])
    assert comum.info.groups == frozenset({"equipe"})

    for groups in (["operadores"], ["group:operadores"], ["equipe", "operadores"]):
        with pytest.raises(RequestRejected) as erro:
            await service.issue(actor=CAIO_KEY, subject="svc:relatorios", groups=groups)
        assert erro.value.field == "groups"
        assert "linha de comando" in str(erro.value)

    pela_cli = await service.issue_as_operator(subject="svc:relatorios", groups=["operadores"])
    assert pela_cli.info.groups == frozenset({"operadores"})


@pytest.mark.parametrize("subject", ["svc:Relatorios", "svc:-x", "svc:", "svc:a b", "svc:" + "a" * 65, "svc:é"])
async def test_nome_do_sistema_fora_do_padrao_e_recusado_nos_dois_caminhos(subject: str) -> None:
    service = access_service()
    with pytest.raises(RequestRejected) as erro:
        await service.issue(actor=CAIO_KEY, subject=subject)
    assert erro.value.field == "subject"
    with pytest.raises(RequestRejected) as erro:
        await service.issue_as_operator(subject=subject)
    assert erro.value.field == "subject"


@pytest.mark.parametrize("subject", ["svc:relatorios.v2_a-b", "svc:9", "svc:" + "a" * 64, "user:Caio.Silva"])
async def test_nomes_no_padrao_sao_aceitos(subject: str) -> None:
    issued = await access_service().issue(actor=CAIO_KEY, subject=subject)
    assert issued.info.subject == subject


async def test_nenhum_registro_contem_a_chave_nem_o_hash(caplog: pytest.LogCaptureFixture) -> None:
    service = access_service()
    with caplog.at_level(logging.DEBUG):
        issued = await service.issue(actor=CAIO_KEY, subject="svc:relatorios")
        rotated = await service.rotate(actor=CAIO_KEY, key_id=issued.info.key_id)
    texto = caplog.text
    for plaintext in (issued.plaintext, rotated.plaintext):
        assert plaintext not in texto
        assert hash_key(plaintext).hex() not in texto
