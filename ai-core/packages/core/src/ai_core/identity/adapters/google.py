"""`UpstreamOidc` real: o Google como provedor OIDC de origem (FR-008; research R9).

Descoberta em cache de 1 h; código trocado com o segredo do cliente e PKCE S256; `id_token` verificado contra o JWKS do
Google (só RS256), com `aud` = client id, `iss` entre os do Google e validade pelo relógio da porta. O `nonce`, o
e-mail verificado e o domínio são decididos no domínio (`domain/google.py`). Qualquer falha vira `UpstreamError`, sem
segredo na mensagem.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Final
from urllib.parse import urlencode

import httpx
import jwt

from ai_core.identity.ports import Clock, GoogleClient, GoogleIdentity, UpstreamError

GOOGLE_DISCOVERY: Final = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_ISSUERS: Final = ("https://accounts.google.com", "accounts.google.com")


class GoogleOidc:
    def __init__(
        self,
        *,
        client: GoogleClient,
        redirect_uri: str,
        http: httpx.AsyncClient,
        clock: Clock,
        discovery_url: str = GOOGLE_DISCOVERY,
        issuers: Sequence[str] = GOOGLE_ISSUERS,
        cache_ttl: timedelta = timedelta(hours=1),
        min_refresh_interval: timedelta = timedelta(seconds=60),
        leeway: timedelta = timedelta(seconds=60),
    ) -> None:
        self._client = client
        self._redirect_uri = redirect_uri
        self._http = http
        self._clock = clock
        self._discovery_url = discovery_url
        self._issuers = frozenset(issuers)
        self._cache_ttl = cache_ttl
        self._min_refresh = min_refresh_interval
        self._leeway = leeway
        self._metadata: dict[str, Any] | None = None
        self._metadata_at: datetime | None = None
        self._keys: dict[str, Any] = {}
        self._keys_at: datetime | None = None

    async def _discover(self) -> dict[str, Any]:
        now = self._clock.now()
        if self._metadata is None or self._metadata_at is None or now - self._metadata_at >= self._cache_ttl:
            try:
                response = await self._http.get(self._discovery_url)
                response.raise_for_status()
                metadata = response.json()
                for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                    if not isinstance(metadata.get(field), str):
                        raise UpstreamError(f"descoberta do Google sem {field}")
            except (httpx.HTTPError, ValueError) as error:
                raise UpstreamError(f"descoberta do Google falhou: {type(error).__name__}") from None
            self._metadata, self._metadata_at = metadata, now
        return self._metadata

    async def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        metadata = await self._discover()
        params = {
            "client_id": self._client.client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        if self._client.hosted_domain:
            params["hd"] = self._client.hosted_domain
        return f"{metadata['authorization_endpoint']}?{urlencode(params)}"

    async def exchange(self, *, code: str, code_verifier: str) -> GoogleIdentity:
        metadata = await self._discover()
        try:
            response = await self._http.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "client_id": self._client.client_id,
                    "client_secret": self._client.client_secret,
                    "code_verifier": code_verifier,
                },
                headers={"accept": "application/json"},
            )
        except httpx.HTTPError as error:
            raise UpstreamError(f"troca de código com o Google falhou: {type(error).__name__}") from None
        if response.status_code != 200:
            raise UpstreamError(f"o Google recusou a troca do código (status {response.status_code})")
        try:
            token = response.json().get("id_token")
        except ValueError:
            token = None
        if not isinstance(token, str):
            raise UpstreamError("resposta do Google sem id_token")
        return self._identity(await self._verify(token, metadata["jwks_uri"]))

    async def _verify(self, token: str, jwks_uri: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise UpstreamError("id_token do Google malformado") from None
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str):
            raise UpstreamError("id_token do Google com algoritmo ou kid inesperado")
        key = await self._key(kid, jwks_uri)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self._client.client_id,
                options={"require": ["iss", "sub", "aud", "exp"], "verify_exp": False, "verify_iat": False},
            )
        except jwt.PyJWTError as error:
            raise UpstreamError(f"id_token do Google inválido: {type(error).__name__}") from None
        if claims.get("iss") not in self._issuers:
            raise UpstreamError("id_token de outro emissor")
        expires = claims.get("exp")
        if (
            not isinstance(expires, int | float)
            or self._clock.now().timestamp() > expires + self._leeway.total_seconds()
        ):
            raise UpstreamError("id_token do Google vencido")
        return claims

    async def _key(self, kid: str, jwks_uri: str) -> Any:
        now = self._clock.now()
        stale = self._keys_at is None or now - self._keys_at >= self._cache_ttl
        recently = self._keys_at is not None and now - self._keys_at < self._min_refresh
        if stale or (kid not in self._keys and not recently):
            try:
                response = await self._http.get(jwks_uri)
                response.raise_for_status()
                keys = {}
                for entry in response.json().get("keys", []):
                    if isinstance(entry, dict) and isinstance(entry.get("kid"), str) and entry.get("kty") == "RSA":
                        try:
                            keys[entry["kid"]] = jwt.PyJWK(entry, algorithm="RS256").key
                        except jwt.PyJWTError:
                            continue
            except (httpx.HTTPError, ValueError, AttributeError) as error:
                raise UpstreamError(f"JWKS do Google indisponível: {type(error).__name__}") from None
            self._keys, self._keys_at = keys, now
        if kid not in self._keys:
            raise UpstreamError("id_token assinado por chave desconhecida")
        return self._keys[kid]

    @staticmethod
    def _identity(claims: dict[str, Any]) -> GoogleIdentity:
        email = claims.get("email")
        verified = claims.get("email_verified")
        hosted = claims.get("hd")
        nonce = claims.get("nonce")
        return GoogleIdentity(
            sub=str(claims["sub"]),
            email=email if isinstance(email, str) else None,
            email_verified=verified is True or verified == "true",
            hosted_domain=hosted if isinstance(hosted, str) else None,
            nonce=nonce if isinstance(nonce, str) else None,
        )
