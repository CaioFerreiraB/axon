"""`TokenSigner` real: RSA-2048 e RS256 com `pyjwt[crypto]` (research R6, R7).

Gera o par, assina com o `kid` no cabeçalho e verifica a assinatura contra um JWKS. Só RS256: `none`, HMAC e qualquer
outro algoritmo são recusados antes de tocar em chave. Tempo, emissor e audiência são do domínio (`domain/tokens.py`).
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping
from typing import Any, Final

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from axon_ai.identity.ports import GeneratedKey

ALGORITHM: Final = "RS256"


class RsaTokenSigner:
    def __init__(self, *, key_size: int = 2048) -> None:
        self._key_size = key_size
        self._private: dict[str, Any] = {}
        self._public: dict[tuple[str, str], Any] = {}

    def generate_key(self) -> GeneratedKey:
        private = rsa.generate_private_key(public_exponent=65537, key_size=self._key_size)
        kid = secrets.token_hex(8)
        public_jwk: dict[str, object] = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
        public_jwk.update(kid=kid, use="sig", alg=ALGORITHM)
        pem = private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return GeneratedKey(kid=kid, public_jwk=public_jwk, private_pem=pem)

    def sign(self, claims: Mapping[str, object], *, kid: str, private_pem: bytes) -> str:
        key = self._private.get(kid)
        if key is None:
            key = serialization.load_pem_private_key(private_pem, password=None)
            if not isinstance(key, rsa.RSAPrivateKey):
                raise ValueError("a chave de assinatura não é RSA")
            self._private[kid] = key
        return jwt.encode(dict(claims), key, algorithm=ALGORITHM, headers={"kid": kid})

    def verify(self, token: str, jwks: Mapping[str, object]) -> Mapping[str, object] | None:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return None
        kid = header.get("kid")
        if header.get("alg") != ALGORITHM or not isinstance(kid, str):
            return None
        key = self._key(kid, jwks)
        if key is None:
            return None
        try:
            claims: dict[str, object] = jwt.decode(
                token,
                key=key,
                algorithms=[ALGORITHM],
                options={
                    "verify_aud": False,
                    "verify_iss": False,
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                },
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            return None
        return claims

    def _key(self, kid: str, jwks: Mapping[str, object]) -> Any:
        entries = jwks.get("keys")
        if not isinstance(entries, list):
            return None
        for entry in entries:
            if not isinstance(entry, Mapping) or entry.get("kid") != kid:
                continue
            if entry.get("kty") != "RSA" or entry.get("alg", ALGORITHM) != ALGORITHM:
                return None
            cache_key = (kid, str(entry.get("n")))
            if cache_key not in self._public:
                try:
                    self._public[cache_key] = jwt.PyJWK(dict(entry), algorithm=ALGORITHM).key
                except jwt.PyJWTError:
                    return None
            return self._public[cache_key]
        return None
