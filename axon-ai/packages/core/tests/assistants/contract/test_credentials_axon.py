"""Credenciais com o nome Axon e a recusa das antigas (US11; FR-024 a FR-026; ADR-037, research R37; T087)."""

from __future__ import annotations

import re
from typing import Any

import pytest
from assistants_testkit import ISSUER, MutableClock, SigningKey, access_service, claims

from axon_ai.assistants.adapters.memory import InMemoryApiKeyStore
from axon_ai.assistants.adapters.oidc import CallableJwksSource, JwksOidcVerifier
from axon_ai.assistants.api import ADMIN_SURFACE, PRIVATE_SURFACE, PUBLIC_SURFACE
from axon_ai.assistants.domain.access import OidcAudiences

pytestmark = pytest.mark.us11

SURFACES = (PUBLIC_SURFACE, PRIVATE_SURFACE, ADMIN_SURFACE)


class Env:
    """O emissor da plataforma em processo e o serviço de acesso com as audiências padrão."""

    def __init__(self) -> None:
        self.signing = SigningKey.rsa()
        verifier = JwksOidcVerifier(issuer=ISSUER, source=CallableJwksSource(lambda: {"keys": [self.signing.jwk()]}))
        self.service = access_service(keys=InMemoryApiKeyStore(), oidc=verifier, clock=MutableClock())

    def token(self, *, audience: str, groups: tuple[str, ...] = ("operadores",)) -> str:
        return self.signing.sign(claims("ana", aud=audience, groups=list(groups)))

    async def authenticate(self, surface: str, credential: str) -> Any:
        return await self.service.authenticate(surface=surface, credential=credential)


@pytest.fixture
async def env() -> Env:
    return Env()


def test_as_audiencias_padrao_sao_as_da_marca() -> None:
    audiences = OidcAudiences()
    assert (audiences.public, audiences.admin) == ("axon", "axon-admin")


async def test_cenario_1_a_chave_emitida_tem_o_prefixo_axn(env: Env) -> None:
    issued = await env.service.issue_as_operator(subject="user:caio", groups=["operadores"])
    assert re.fullmatch(r"axn_[0-9a-f]{16}_\S+", issued.plaintext)
    for surface in (PRIVATE_SURFACE, ADMIN_SURFACE):
        principal = await env.authenticate(surface, issued.plaintext)
        assert principal is not None and principal.scheme == "api_key" and env.service.is_admin(principal)


async def test_cenario_2_chave_no_formato_antigo_nao_autentica(env: Env) -> None:
    issued = await env.service.issue_as_operator(subject="user:caio", groups=["operadores"])
    antigas = ("aic_" + issued.plaintext.removeprefix("axn_"), "aic_0123456789abcdef_segredo")
    for credential in antigas:
        for surface in (PRIVATE_SURFACE, ADMIN_SURFACE):
            assert await env.authenticate(surface, credential) is None, (surface, credential)


async def test_cenario_3_token_do_chat_so_vale_na_publica(env: Env) -> None:
    chat = env.token(audience="axon")
    assert await env.authenticate(PUBLIC_SURFACE, chat) is not None
    assert await env.authenticate(ADMIN_SURFACE, chat) is None


async def test_cenario_4_token_da_console_de_admin_administra(env: Env) -> None:
    principal = await env.authenticate(ADMIN_SURFACE, env.token(audience="axon-admin"))
    assert principal is not None and principal.scheme == "oidc" and env.service.is_admin(principal)


@pytest.mark.parametrize("audience", ["ai-core", "ai-core-admin"])
async def test_cenario_5_token_com_audiencia_antiga_nao_autentica(env: Env, audience: str) -> None:
    token = env.token(audience=audience)
    for surface in SURFACES:
        assert await env.authenticate(surface, token) is None, surface
