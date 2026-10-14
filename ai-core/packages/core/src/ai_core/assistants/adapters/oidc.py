"""`OidcVerifier` real: verificação local de JWT contra o JWKS do emissor (research R6, R26).

Confere assinatura, algoritmo, emissor e audiência — a da superfície, a cada chamada —, e exige `sub` e `exp`. **Não**
confere `exp`, `nbf` nem `iat`: o tempo é do domínio, com o relógio da porta. A lista de algoritmos é fechada e só de
assimétricos — `none` e HMAC são recusados antes de tocar em chave, o que fecha a confusão de algoritmo (token HMAC
assinado com a chave pública).

De onde vêm as chaves é uma fonte plugável (`JwksSource`, Fase 9): `HttpJwksSource` busca o JWKS de um provedor externo
(descoberta ou URL configurada), com cache e nova busca para `kid` desconhecido limitada por um intervalo mínimo;
`CallableJwksSource` lê uma função em processo — o `jwks()` do seam `PublicKeySet` da 012, injetado pela 011, sem a
plataforma chamar a si mesma pela rede (ADR-030). Qualquer falha — rede, JSON, chave — devolve `None`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol

import httpx
import jwt

from ai_core.assistants.ports import Clock

DEFAULT_ALGORITHMS: tuple[str, ...] = ("RS256", "ES256")
_ASYMMETRIC_PREFIXES = ("RS", "ES", "PS")


class JwksSource(Protocol):
    """De onde vem o JWKS. Interna ao adapter (contracts/ports.md): a 011 escolhe uma das duas."""

    async def jwks(self, *, kid: str) -> Mapping[str, object] | None:
        """O JWKS que deve conter `kid`; a fonte decide quando buscar de novo. `None` = indisponível."""
        ...


class HttpJwksSource:
    """JWKS de um provedor externo, por descoberta ou por URL configurada, com cache."""

    def __init__(
        self,
        *,
        issuer: str,
        client: httpx.AsyncClient,
        clock: Clock,
        jwks_url: str | None = None,
        cache_ttl: timedelta = timedelta(minutes=10),
        min_refresh_interval: timedelta = timedelta(seconds=60),
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._client = client
        self._clock = clock
        self._jwks_url = jwks_url
        self._cache_ttl = cache_ttl
        self._min_refresh = min_refresh_interval
        self._document: Mapping[str, object] | None = None
        self._kids: frozenset[str] = frozenset()
        self._fetched_at: datetime | None = None
        self._attempted_at: datetime | None = None

    async def jwks(self, *, kid: str) -> Mapping[str, object] | None:
        now = self._clock.now()
        expired = self._fetched_at is None or now - self._fetched_at >= self._cache_ttl
        if expired or kid not in self._kids:
            await self._refresh(now)
        return self._document

    async def _refresh(self, now: datetime) -> None:
        if self._attempted_at is not None and now - self._attempted_at < self._min_refresh:
            return
        self._attempted_at = now
        try:
            url = self._jwks_url or await self._discover()
            response = await self._client.get(url)
            response.raise_for_status()
            document = response.json()
            entries = document["keys"]
            kids = frozenset(entry["kid"] for entry in entries if isinstance(entry.get("kid"), str))
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            return
        self._document, self._kids, self._fetched_at = document, kids, now

    async def _discover(self) -> str:
        response = await self._client.get(f"{self._issuer}/.well-known/openid-configuration")
        response.raise_for_status()
        url = response.json()["jwks_uri"]
        if not isinstance(url, str):
            raise ValueError("jwks_uri ausente no documento de descoberta")
        self._jwks_url = url
        return url


class CallableJwksSource:
    """JWKS em processo: uma função sem I/O, sempre atual (o `PublicKeySet.jwks` da 012)."""

    def __init__(self, function: Callable[[], Mapping[str, object]]) -> None:
        self._function = function

    async def jwks(self, *, kid: str) -> Mapping[str, object] | None:
        return self._function()


class JwksOidcVerifier:
    """Verificador de tokens de um emissor, com as chaves da fonte dada."""

    def __init__(
        self,
        *,
        issuer: str,
        source: JwksSource,
        algorithms: Sequence[str] = DEFAULT_ALGORITHMS,
    ) -> None:
        unsafe = [alg for alg in algorithms if not alg.startswith(_ASYMMETRIC_PREFIXES)]
        if unsafe:
            raise ValueError(f"só algoritmos assimétricos são aceitos: {', '.join(unsafe)}")
        self._issuer = issuer.rstrip("/")
        self._source = source
        self._algorithms = frozenset(algorithms)
        self._parsed: dict[tuple[str, str], tuple[Any, str | None]] = {}

    async def verify(self, token: str, *, audience: str) -> Mapping[str, object] | None:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return None
        alg, kid = header.get("alg"), header.get("kid")
        if alg not in self._algorithms or not isinstance(kid, str):
            return None
        found = self._key(kid, await self._source.jwks(kid=kid))
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
                audience=audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub"], "verify_exp": False, "verify_nbf": False, "verify_iat": False},
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            return None
        return claims

    def _key(self, kid: str, document: Mapping[str, object] | None) -> tuple[Any, str | None] | None:
        entries = document.get("keys") if document is not None else None
        if not isinstance(entries, list):
            return None
        for entry in entries:
            # Só chaves de assinatura. Uma entrada que não serve para verificar — a de cifragem (`use: enc`,
            # `RSA-OAEP`) que o Keycloak sempre publica, ou uma malformada — é ignorada sozinha: descartar o JWKS
            # inteiro por ela recusaria todo token do provedor (research R24).
            if not isinstance(entry, Mapping) or entry.get("kid") != kid or entry.get("use", "sig") != "sig":
                continue
            fingerprint = (kid, str(entry.get("n") or entry.get("x") or ""))
            if fingerprint not in self._parsed:
                try:
                    self._parsed[fingerprint] = (jwt.PyJWK(dict(entry)).key, entry.get("alg"))
                except jwt.PyJWTError:
                    continue
            return self._parsed[fingerprint]
        return None
