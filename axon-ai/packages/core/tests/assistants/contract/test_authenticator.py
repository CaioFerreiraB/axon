"""T022 — conformidade do seam `Authenticator` (contracts/assistants-api.md).

Roda com os dois verificadores OIDC (estático e JWKS) e os dois armazenamentos de chave (memória e Postgres): o seam
se comporta igual com qualquer adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from assistants_testkit import ISSUER, JwksServer, MutableClock, SigningKey, access_service, claims

from axon_ai.assistants.adapters.memory import StaticOidcVerifier
from axon_ai.assistants.adapters.oidc import HttpJwksSource, JwksOidcVerifier
from axon_ai.assistants.api import Principal


@dataclass
class Case:
    service: Any
    token: str
    key: str
    clock: MutableClock


@pytest.fixture(params=["estatico", "jwks"])
async def case(request: pytest.FixtureRequest, api_key_store: Any) -> Case:
    clock = MutableClock()
    data = claims("ana", groups=["chefia"], ttl=300)
    if request.param == "estatico":
        token = "token-da-ana"
        oidc: Any = StaticOidcVerifier({token: data})
    else:
        signing = SigningKey.rsa()
        server = JwksServer(keys=[signing])
        token = signing.sign(data)
        source = HttpJwksSource(issuer=ISSUER, client=server.client(), clock=clock)
        oidc = JwksOidcVerifier(issuer=ISSUER, source=source)
    service = access_service(keys=api_key_store, oidc=oidc, clock=clock)
    issued = await service.issue_as_operator(subject="user:caio", groups=["operadores"], label="teste")
    return Case(service=service, token=token, key=issued.plaintext, clock=clock)


async def test_token_oidc_na_superficie_publica_vira_principal(case: Case) -> None:
    principal = await case.service.authenticate(surface="public", credential=case.token)
    assert principal == Principal(subject="user:ana", scheme="oidc", groups=frozenset({"chefia"}))


async def test_chave_na_superficie_privada_vira_o_dono(case: Case) -> None:
    principal = await case.service.authenticate(surface="private", credential=case.key)
    assert principal == Principal(subject="user:caio", scheme="api_key", groups=frozenset({"operadores"}))


async def test_os_dois_principals_sao_distintos(case: Case) -> None:
    publico = await case.service.authenticate(surface="public", credential=case.token)
    privado = await case.service.authenticate(surface="private", credential=case.key)
    assert publico != privado


async def test_credencial_trocada_de_superficie_e_recusada(case: Case) -> None:
    assert await case.service.authenticate(surface="private", credential=case.token) is None
    assert await case.service.authenticate(surface="public", credential=case.key) is None


@pytest.mark.parametrize("surface", ["public", "private"])
@pytest.mark.parametrize("credential", [None, "", "   "])
async def test_credencial_ausente_e_recusada_sem_levantar(case: Case, surface: str, credential: str | None) -> None:
    assert await case.service.authenticate(surface=surface, credential=credential) is None


async def test_chave_malformada_adulterada_ou_desconhecida_e_recusada(case: Case) -> None:
    adulterada = case.key[:-1] + ("A" if case.key[-1] != "A" else "B")
    desconhecida = "axn_00000000000000ff_segredo"
    for credential in ("axn_zzz", adulterada, desconhecida, f"Bearer {case.key}"):
        assert await case.service.authenticate(surface="private", credential=credential) is None


async def test_token_expirado_e_recusado(case: Case) -> None:
    case.clock.advance(400)  # ttl 300 + tolerância 60
    assert await case.service.authenticate(surface="public", credential=case.token) is None


async def test_chave_revogada_e_recusada_na_chamada_seguinte(case: Case) -> None:
    principal = await case.service.authenticate(surface="private", credential=case.key)
    assert principal is not None
    (info,) = await case.service.keys_as_operator()
    await case.service.revoke_as_operator(key_id=info.key_id)
    assert await case.service.authenticate(surface="private", credential=case.key) is None


async def test_superficie_desconhecida_e_recusada(case: Case) -> None:
    assert await case.service.authenticate(surface="outra", credential=case.key) is None
