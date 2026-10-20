"""T020 — conformidade da porta `OidcVerifier` (contracts/ports.md): estático, JWKS e desligado.

O JWKS é servido por `httpx.MockTransport` com chaves geradas na suíte — sem provedor externo. O verificador confere
assinatura, algoritmo, emissor e audiência; o tempo do token é do domínio (research R6).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
import pytest
from assistants_testkit import AUDIENCE, ISSUER, JwksServer, MutableClock, SigningKey, claims, forge

from axon_ai.assistants.adapters.memory import DisabledOidcVerifier, StaticOidcVerifier
from axon_ai.assistants.adapters.oidc import CallableJwksSource, HttpJwksSource, JwksOidcVerifier


class _Verifier:
    """O verificador real com a fonte HTTP, chamado com a audiência da suíte."""

    def __init__(self, server: JwksServer, clock: MutableClock, *, explicit_url: bool) -> None:
        source = HttpJwksSource(
            issuer=ISSUER, client=server.client(), clock=clock, jwks_url=server.jwks_url if explicit_url else None
        )
        self.real = JwksOidcVerifier(issuer=ISSUER, source=source)

    async def verify(self, token: str) -> Any:
        return await self.real.verify(token, audience=AUDIENCE)


def _verifier(server: JwksServer, clock: MutableClock, *, explicit_url: bool = False) -> _Verifier:
    return _Verifier(server, clock, explicit_url=explicit_url)


@pytest.fixture(params=["rsa", "ec"])
def key(request: pytest.FixtureRequest) -> SigningKey:
    return SigningKey.rsa() if request.param == "rsa" else SigningKey.ec()


# --- estático e desligado --------------------------------------------------------------------------------------------


async def test_estatico_devolve_as_claims_do_token_conhecido_na_audiencia_certa() -> None:
    verifier = StaticOidcVerifier({"token-ana": claims("ana")})
    assert (await verifier.verify("token-ana", audience=AUDIENCE) or {}).get("sub") == "ana"
    assert await verifier.verify("outro", audience=AUDIENCE) is None
    assert await verifier.verify("token-ana", audience="ai-core-admin") is None


async def test_desligado_recusa_tudo() -> None:
    assert await DisabledOidcVerifier().verify("qualquer", audience=AUDIENCE) is None


# --- JWKS ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("explicit_url", [False, True])
async def test_jwks_token_bom_devolve_claims(key: SigningKey, clock: MutableClock, explicit_url: bool) -> None:
    server = JwksServer(keys=[key])
    verifier = _verifier(server, clock, explicit_url=explicit_url)

    result = await verifier.verify(key.sign(claims("ana", groups=["chefia"])))

    assert result is not None and result["sub"] == "ana" and result["groups"] == ["chefia"]
    discovery = f"{ISSUER}/.well-known/openid-configuration"
    assert (discovery in server.requests) is not explicit_url


async def test_jwks_nao_confere_o_tempo_que_e_do_dominio(key: SigningKey, clock: MutableClock) -> None:
    expirado = claims("ana", ttl=1)
    clock.advance(3600)
    assert await _verifier(JwksServer(keys=[key]), clock).verify(key.sign(expirado)) is not None


@pytest.mark.parametrize(
    "ajuste",
    [
        {"iss": "https://outro-idp.test"},
        {"aud": "outra-api"},
    ],
)
async def test_jwks_emissor_ou_audiencia_errados_recusam(
    key: SigningKey, clock: MutableClock, ajuste: dict[str, Any]
) -> None:
    token = key.sign({**claims("ana"), **ajuste})
    assert await _verifier(JwksServer(keys=[key]), clock).verify(token) is None


async def test_jwks_sem_sub_recusa(key: SigningKey, clock: MutableClock) -> None:
    data = claims("ana")
    del data["sub"]
    assert await _verifier(JwksServer(keys=[key]), clock).verify(key.sign(data)) is None


async def test_jwks_assinatura_de_outra_chave_com_o_mesmo_kid_recusa(clock: MutableClock) -> None:
    publicada = SigningKey.rsa(kid="k1")
    impostora = SigningKey.rsa(kid="k1")
    assert await _verifier(JwksServer(keys=[publicada]), clock).verify(impostora.sign(claims("ana"))) is None


async def test_jwks_alg_none_recusa(key: SigningKey, clock: MutableClock) -> None:
    token = forge({"alg": "none", "kid": key.kid, "typ": "JWT"}, claims("ana"))
    assert await _verifier(JwksServer(keys=[key]), clock).verify(token) is None


async def test_jwks_hs256_assinado_com_a_chave_publica_recusa(clock: MutableClock) -> None:
    """Confusão de algoritmo: o atacante usa a chave pública publicada como segredo HMAC."""
    key = SigningKey.rsa()
    token = forge({"alg": "HS256", "kid": key.kid, "typ": "JWT"}, claims("ana"), hmac_secret=key.public_pem())
    assert await _verifier(JwksServer(keys=[key]), clock).verify(token) is None


async def test_jwks_alg_do_cabecalho_diferente_do_da_chave_recusa(clock: MutableClock) -> None:
    rsa_key = SigningKey.rsa(kid="k1")
    ec_key = SigningKey.ec(kid="k1")
    assert await _verifier(JwksServer(keys=[rsa_key]), clock).verify(ec_key.sign(claims("ana"))) is None


async def test_jwks_token_malformado_recusa(clock: MutableClock) -> None:
    verifier = _verifier(JwksServer(keys=[SigningKey.rsa()]), clock)
    for token in ("", "abc", "a.b.c", "Bearer x.y.z"):
        assert await verifier.verify(token) is None


async def test_jwks_kid_desconhecido_busca_de_novo_respeitando_o_intervalo(clock: MutableClock) -> None:
    antiga, nova = SigningKey.rsa(kid="k1"), SigningKey.rsa(kid="k2")
    server = JwksServer(keys=[antiga])
    verifier = _verifier(server, clock)

    assert await verifier.verify(antiga.sign(claims("ana"))) is not None
    assert server.jwks_fetches == 1

    server.keys = [antiga, nova]  # rotação no provedor
    assert await verifier.verify(nova.sign(claims("ana"))) is None  # dentro do intervalo mínimo: não busca de novo
    assert server.jwks_fetches == 1

    clock.advance(61)
    assert await verifier.verify(nova.sign(claims("ana", at=clock.now()))) is not None
    assert server.jwks_fetches == 2


async def test_jwks_cache_expira_e_busca_de_novo(clock: MutableClock) -> None:
    key = SigningKey.rsa()
    server = JwksServer(keys=[key])
    verifier = _verifier(server, clock)
    await verifier.verify(key.sign(claims("ana")))
    await verifier.verify(key.sign(claims("ana")))
    assert server.jwks_fetches == 1
    clock.advance(timedelta(minutes=11).total_seconds())
    await verifier.verify(key.sign(claims("ana", at=clock.now())))
    assert server.jwks_fetches == 2


async def test_jwks_provedor_fora_do_ar_recusa_sem_levantar(clock: MutableClock) -> None:
    def fora(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota", request=request)

    source = HttpJwksSource(issuer=ISSUER, client=httpx.AsyncClient(transport=httpx.MockTransport(fora)), clock=clock)
    verifier = JwksOidcVerifier(issuer=ISSUER, source=source)
    assert await verifier.verify(SigningKey.rsa().sign(claims("ana")), audience=AUDIENCE) is None


# --- Ajuste de 2026-10-13 (002 passada da Fase 7): JWKS com chave que não é de assinatura ----------------------------


async def test_jwks_com_chave_de_cifragem_ainda_verifica_as_de_assinatura(clock: MutableClock) -> None:
    """O Keycloak publica, ao lado das chaves de assinatura, uma de cifragem (`use: enc`, `RSA-OAEP`) que o PyJWT não
    carrega como chave de verificação. Uma entrada assim é ignorada — antes, ela descartava o JWKS inteiro e todo token
    era recusado."""
    key = SigningKey.rsa(kid="sig-1")
    cifragem = {**SigningKey.rsa(kid="enc-1").jwk(), "alg": "RSA-OAEP", "use": "enc"}
    quebrada = {"kid": "quebrada", "kty": "RSA", "alg": "RS256"}
    server = JwksServer(keys=[key], extra=[cifragem, quebrada])

    result = await _verifier(server, clock).verify(key.sign(claims("ana")))

    assert result is not None and result["sub"] == "ana"


async def test_jwks_token_assinado_com_chave_de_cifragem_recusa(clock: MutableClock) -> None:
    """A chave marcada `use: enc` não vale para verificar assinatura, nem se o token a nomear."""
    impostora = SigningKey.rsa(kid="enc-1")
    publicada = {**impostora.jwk(), "use": "enc"}
    server = JwksServer(keys=[SigningKey.rsa(kid="sig-1")], extra=[publicada])
    assert await _verifier(server, clock).verify(impostora.sign(claims("ana"))) is None


# --- Fase 9 (T069): fonte em processo e audiência por chamada -------------------------------------------------------


async def test_fonte_em_processo_acompanha_a_rotacao_sem_rede() -> None:
    antiga, nova = SigningKey.rsa(kid="k1"), SigningKey.rsa(kid="k2")
    published = {"keys": [antiga.jwk()]}
    verifier = JwksOidcVerifier(issuer=ISSUER, source=CallableJwksSource(lambda: published))
    assert await verifier.verify(antiga.sign(claims("ana")), audience=AUDIENCE) is not None
    assert await verifier.verify(nova.sign(claims("ana")), audience=AUDIENCE) is None
    published["keys"] = [antiga.jwk(), nova.jwk()]
    assert await verifier.verify(nova.sign(claims("ana")), audience=AUDIENCE) is not None


async def test_audiencia_e_conferida_a_cada_chamada(key: SigningKey) -> None:
    verifier = JwksOidcVerifier(issuer=ISSUER, source=CallableJwksSource(lambda: {"keys": [key.jwk()]}))
    chat = key.sign(claims("ana"))
    console = key.sign(claims("ana", aud="ai-core-admin"))
    assert await verifier.verify(chat, audience=AUDIENCE) is not None
    assert await verifier.verify(chat, audience="ai-core-admin") is None
    assert await verifier.verify(console, audience="ai-core-admin") is not None
    assert await verifier.verify(console, audience=AUDIENCE) is None
