"""`OidcVerifier` real: verificação local de JWT contra o JWKS do provedor (research R6).

Confere assinatura, algoritmo, emissor e audiência, e exige `sub` e `exp`. **Não** confere `exp`, `nbf` nem `iat`: o
tempo é do domínio, com o relógio da porta. A lista de algoritmos é fechada e só de assimétricos — `none` e HMAC são
recusados antes de tocar em chave, o que fecha a confusão de algoritmo (token HMAC assinado com a chave pública).

O JWKS fica em cache; um `kid` desconhecido dispara nova busca, limitada por um intervalo mínimo para que tokens com
`kid` inventado não virem tráfego contra o provedor. Qualquer falha — rede, JSON, chave — devolve `None`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

import httpx
import jwt

from ai_core.assistants.ports import Clock

DEFAULT_ALGORITHMS: tuple[str, ...] = ("RS256", "ES256")
_ASYMMETRIC_PREFIXES = ("RS", "ES", "PS")


class JwksOidcVerifier:
    """Verificador de tokens de um emissor, com JWKS por descoberta ou por URL configurada."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        client: httpx.AsyncClient,
        clock: Clock,
        jwks_url: str | None = None,
        algorithms: Sequence[str] = DEFAULT_ALGORITHMS,
        cache_ttl: timedelta = timedelta(minutes=10),
        min_refresh_interval: timedelta = timedelta(seconds=60),
    ) -> None:
        unsafe = [alg for alg in algorithms if not alg.startswith(_ASYMMETRIC_PREFIXES)]
        if unsafe:
            raise ValueError(f"só algoritmos assimétricos são aceitos: {', '.join(unsafe)}")
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._client = client
        self._clock = clock
        self._jwks_url = jwks_url
        self._algorithms = frozenset(algorithms)
        self._cache_ttl = cache_ttl
        self._min_refresh = min_refresh_interval
        self._keys: dict[str, tuple[Any, str | None]] = {}
        self._fetched_at: datetime | None = None
        self._attempted_at: datetime | None = None

    async def verify(self, token: str) -> Mapping[str, object] | None:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return None
        alg, kid = header.get("alg"), header.get("kid")
        if alg not in self._algorithms or not isinstance(kid, str):
            return None
        found = await self._key(kid)
        if found is None:
            return None
        key, declared = found
        if declared is not None and declared != alg:
            return None
        try:
            claims: dict[str, object] = jwt.decode(
                token,
                key=key,
                algorithms=[alg],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub"], "verify_exp": False, "verify_nbf": False, "verify_iat": False},
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            return None
        return claims

    async def _key(self, kid: str) -> tuple[Any, str | None] | None:
        now = self._clock.now()
        expired = self._fetched_at is None or now - self._fetched_at >= self._cache_ttl
        if expired or kid not in self._keys:
            await self._refresh(now)
        return self._keys.get(kid)

    async def _refresh(self, now: datetime) -> None:
        if self._attempted_at is not None and now - self._attempted_at < self._min_refresh:
            return
        self._attempted_at = now
        try:
            url = self._jwks_url or await self._discover()
            response = await self._client.get(url)
            response.raise_for_status()
            entries = response.json()["keys"]
            keys: dict[str, tuple[Any, str | None]] = {}
            for entry in entries:
                kid = entry.get("kid")
                if isinstance(kid, str):
                    keys[kid] = (jwt.PyJWK(entry).key, entry.get("alg"))
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, jwt.PyJWTError):
            return
        self._keys = keys
        self._fetched_at = now

    async def _discover(self) -> str:
        response = await self._client.get(f"{self._issuer}/.well-known/openid-configuration")
        response.raise_for_status()
        url = response.json()["jwks_uri"]
        if not isinstance(url, str):
            raise ValueError("jwks_uri ausente no documento de descoberta")
        self._jwks_url = url
        return url
