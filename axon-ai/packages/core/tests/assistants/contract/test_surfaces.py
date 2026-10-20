"""T068 — as três superfícies (US9; ADR-031, research R25 a R27): esquemas, audiência e admin por grupo."""

from __future__ import annotations

from typing import Any

import pytest
from assistants_testkit import AUDIENCE, ISSUER, MutableClock, SigningKey, access_service, claims

from axon_ai.assistants.adapters.memory import InMemoryApiKeyStore
from axon_ai.assistants.adapters.oidc import CallableJwksSource, JwksOidcVerifier
from axon_ai.assistants.api import (
    ADMIN_SURFACE,
    PRIVATE_SURFACE,
    PUBLIC_SURFACE,
    SCHEME_OF_SURFACE,
    SCHEMES_OF_SURFACE,
)
from axon_ai.assistants.domain.access import OidcAudiences

pytestmark = pytest.mark.us9

ADMIN_AUDIENCE = "ai-core-admin"


class Env:
    """Um emissor (a 012, em processo), o serviço de acesso e as credenciais da US9."""

    def __init__(self) -> None:
        self.clock = MutableClock()
        self.signing = SigningKey.rsa()
        verifier = JwksOidcVerifier(issuer=ISSUER, source=CallableJwksSource(lambda: {"keys": [self.signing.jwk()]}))
        self.service = access_service(keys=InMemoryApiKeyStore(), oidc=verifier, clock=self.clock)

    def token(self, sub: str, *, audience: str, groups: list[str]) -> str:
        return self.signing.sign(claims(sub, aud=audience, groups=groups))

    async def authenticate(self, surface: str, credential: str) -> Any:
        return await self.service.authenticate(surface=surface, credential=credential)


@pytest.fixture
async def env() -> Env:
    return Env()


def test_esquemas_por_superficie_e_o_mapa_antigo_derivado() -> None:
    assert {
        PUBLIC_SURFACE: frozenset({"oidc"}),
        PRIVATE_SURFACE: frozenset({"api_key"}),
        ADMIN_SURFACE: frozenset({"oidc", "api_key"}),
    } == SCHEMES_OF_SURFACE
    assert dict(SCHEME_OF_SURFACE) == {PUBLIC_SURFACE: "oidc", PRIVATE_SURFACE: "api_key"}
    assert OidcAudiences().of(PUBLIC_SURFACE) == AUDIENCE and OidcAudiences().of(ADMIN_SURFACE) == ADMIN_AUDIENCE
    assert OidcAudiences().of(PRIVATE_SURFACE) is None


async def test_cenario_1_token_da_console_de_admin_e_admin(env: Env) -> None:
    principal = await env.authenticate(ADMIN_SURFACE, env.token("ana", audience=ADMIN_AUDIENCE, groups=["operadores"]))
    assert principal is not None and principal.scheme == "oidc" and env.service.is_admin(principal)


async def test_cenario_2_token_do_chat_nao_vale_na_administracao(env: Env) -> None:
    chat = env.token("ana", audience=AUDIENCE, groups=["operadores"])
    assert await env.authenticate(ADMIN_SURFACE, chat) is None
    assert await env.authenticate(PUBLIC_SURFACE, chat) is not None


async def test_token_da_console_nao_vale_no_chat(env: Env) -> None:
    console = env.token("ana", audience=ADMIN_AUDIENCE, groups=["operadores"])
    assert await env.authenticate(PUBLIC_SURFACE, console) is None


async def test_cenario_3_nao_admin_autentica_mas_nao_administra(env: Env) -> None:
    principal = await env.authenticate(ADMIN_SURFACE, env.token("bia", audience=ADMIN_AUDIENCE, groups=["equipe"]))
    assert principal is not None and not env.service.is_admin(principal)


async def test_cenario_4_chave_de_admin_vale_na_administracao_e_na_privada(env: Env) -> None:
    issued = await env.service.issue_as_operator(subject="user:caio", groups=["operadores"])
    for surface in (ADMIN_SURFACE, PRIVATE_SURFACE):
        principal = await env.authenticate(surface, issued.plaintext)
        assert principal is not None and principal.scheme == "api_key" and env.service.is_admin(principal)
    assert await env.authenticate(PUBLIC_SURFACE, issued.plaintext) is None


@pytest.mark.parametrize("credential", ["", "lixo", "aic_0000000000000000_inventada", "a.b.c"])
async def test_credencial_invalida_nao_autentica(env: Env, credential: str) -> None:
    assert await env.authenticate(ADMIN_SURFACE, credential) is None


async def test_token_oidc_na_privada_continua_recusado(env: Env) -> None:
    token = env.token("ana", audience=ADMIN_AUDIENCE, groups=["operadores"])
    assert await env.authenticate(PRIVATE_SURFACE, token) is None
