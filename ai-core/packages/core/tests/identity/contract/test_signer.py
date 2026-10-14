"""T015 — `TokenSigner`: RSA-2048, RS256 com `kid` e verificação contra um JWKS; `none` e HMAC recusados."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re

import jwt
from identity_testkit import shared_signer

from ai_core.identity.adapters.signing import RsaTokenSigner


def _b64(data: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_gera_par_com_kid_de_16_hex_e_jwk_publica() -> None:
    key = shared_signer().generate_key()
    assert re.fullmatch(r"[0-9a-f]{16}", key.kid)
    assert key.public_jwk["kid"] == key.kid and key.public_jwk["alg"] == "RS256" and key.public_jwk["use"] == "sig"
    assert key.public_jwk["kty"] == "RSA" and "d" not in key.public_jwk
    assert key.private_pem.startswith(b"-----BEGIN PRIVATE KEY-----")
    assert "redigido" in repr(key)


def test_assina_com_kid_e_verifica_contra_o_jwks() -> None:
    signer = shared_signer()
    key = signer.generate_key()
    token = signer.sign({"sub": "x", "aud": "ai-core"}, kid=key.kid, private_pem=key.private_pem)
    assert jwt.get_unverified_header(token) == {"alg": "RS256", "kid": key.kid, "typ": "JWT"}
    jwks = {"keys": [dict(key.public_jwk)]}
    assert signer.verify(token, jwks) == {"sub": "x", "aud": "ai-core"}
    # outro assinador (outro processo) verifica só com o JWKS
    assert RsaTokenSigner().verify(token, jwks) == {"sub": "x", "aud": "ai-core"}


def test_recusa_kid_desconhecido_assinatura_alterada_none_e_hmac() -> None:
    signer = shared_signer()
    key, other = signer.generate_key(), signer.generate_key()
    token = signer.sign({"sub": "x"}, kid=key.kid, private_pem=key.private_pem)
    jwks = {"keys": [dict(key.public_jwk)]}
    assert signer.verify(token, {"keys": [dict(other.public_jwk)]}) is None
    head, _, signature = token.split(".")
    assert signer.verify(f"{head}.{_b64({'sub': 'admin'})}.{signature}", jwks) is None
    none_token = f"{_b64({'alg': 'none', 'kid': key.kid})}.{_b64({'sub': 'x'})}."
    assert signer.verify(none_token, jwks) is None
    # confusão de algoritmo: HMAC com o material público como segredo
    signing_input = f"{_b64({'alg': 'HS256', 'kid': key.kid})}.{_b64({'sub': 'admin'})}"
    mac = hmac.new(str(key.public_jwk["n"]).encode(), signing_input.encode(), hashlib.sha256).digest()
    hmac_token = f"{signing_input}.{base64.urlsafe_b64encode(mac).rstrip(b'=').decode()}"
    assert signer.verify(hmac_token, jwks) is None
    assert signer.verify("não é jwt", jwks) is None
    assert signer.verify(token, {"keys": "x"}) is None
