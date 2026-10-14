"""T060 — conformidade do seam `PublicKeySet` e da rotação de chaves (memória e Postgres; FR-016, FR-017; SC-007)."""

from __future__ import annotations

from datetime import timedelta

import httpx
from identity_testkit import CONSOLE, Harness, account

from ai_core.identity.adapters.signing import RsaTokenSigner
from ai_core.identity.ports import Session


async def _session(seam: Harness) -> str:
    await seam.add_account("ana")
    now = seam.clock.now()
    await seam.grants.create_session(
        Session(
            id_hash="s1",
            account_id="id-ana",
            auth_time=now,
            amr="pwd",
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    return "s1"


def _access(seam: Harness) -> str:
    response = seam.service._tokens_response(
        CONSOLE, account("ana").account, scope="openid", nonce=None, auth_time=seam.clock.now(), amr="pwd", refresh="r"
    )
    return str(response.body["access_token"])


async def test_rotacao_normal_mantem_a_anterior_publicada(seam: Harness) -> None:
    session = await _session(seam)
    first = seam.service.jwks()["keys"]
    assert len(first) == 1
    token_before = _access(seam)
    # a rotação acontece depois da emissão — com o relógio parado, as duas chaves nasceriam no mesmo instante e a
    # ordem do JWKS dependeria do desempate de cada armazenamento
    seam.clock.advance(timedelta(minutes=1))
    new_kid = await seam.service.rotate_keys()
    published = [key["kid"] for key in seam.service.jwks()["keys"]]
    assert published == [first[0]["kid"], new_kid]
    # o token emitido antes da rotação continua verificável, e nenhuma sessão caiu (SC-007)
    assert RsaTokenSigner().verify(token_before, seam.service.jwks()) is not None
    assert (await seam.grants.get_session(session)).revoked_at is None
    token_after = _access(seam)
    assert token_after.split(".")[0] != token_before.split(".")[0]


async def test_em_retirada_sai_depois_do_prazo(seam: Harness) -> None:
    old = seam.service.jwks()["keys"][0]["kid"]
    await seam.service.rotate_keys()
    seam.clock.advance(timedelta(minutes=10))
    await seam.service.purge()
    assert old in [key["kid"] for key in seam.service.jwks()["keys"]]
    seam.clock.advance(timedelta(minutes=1))
    await seam.service.purge()
    remaining = [key["kid"] for key in seam.service.jwks()["keys"]]
    assert len(remaining) == 1 and old not in remaining
    states = {key.kid: key.state for key in await seam.keys.all()}
    assert states[old] == "retired"


async def test_rotacao_forcada_troca_tudo_e_encerra_as_sessoes(seam: Harness) -> None:
    session = await _session(seam)
    old = seam.service.jwks()["keys"][0]["kid"]
    token_before = _access(seam)
    new_kid = await seam.service.rotate_keys(force=True)
    assert [key["kid"] for key in seam.service.jwks()["keys"]] == [new_kid] and new_kid != old
    assert RsaTokenSigner().verify(token_before, seam.service.jwks()) is None
    assert (await seam.grants.get_session(session)).revoked_at is not None


async def test_o_armazenamento_nunca_recebe_a_privada_em_claro(seam: Harness) -> None:
    await seam.service.rotate_keys()
    for key in await seam.keys.all():
        assert b"PRIVATE KEY" not in key.private_sealed and key.private_sealed[:1] == b"\x01"
        assert "d" not in key.public_jwk and "p" not in key.public_jwk


async def test_endpoint_publica_o_mesmo_conjunto(started: Harness, http: httpx.AsyncClient) -> None:
    response = await http.get("/oauth2/jwks")
    assert response.json() == started.service.jwks()
    assert response.headers["cache-control"] == "public, max-age=300"
