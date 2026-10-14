"""Fábricas dos testes da 003: configuração, Principals, registry de packs falso, relógio, JWT e serviços montados.

Tudo o que é infraestrutura de verdade (Postgres, JWKS por HTTP) entra por fixture no `conftest.py`; aqui só há dados e
dublês. Os construtores de configuração devolvem mapeamentos válidos por default, sobrescrevíveis por campo — cada
teste declara só o que o distingue.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from ai_core.assistants.api import Principal
from ai_core.packs.api import (
    Composition,
    CompositionError,
    PackCapabilities,
    PackEntry,
    PackStatus,
    RetrieverCapability,
)

T0 = datetime(2026, 9, 30, 12, tzinfo=UTC)
"""Instante inicial do relógio das suítes."""

FLOWS = frozenset({"chat", "agentic"})
"""Nomes de flow que o motor "oferece" nas suítes."""

ISSUER = "https://idp.exemplo.test"
AUDIENCE = "ai-core"


# ---------------------------------------------------------------------------------------------------------------------
# Principals
# ---------------------------------------------------------------------------------------------------------------------

ANA = Principal(subject="user:ana", scheme="oidc")
"""Usuária pública, sem grupos."""

BIA = Principal(subject="user:bia", scheme="oidc", groups=frozenset({"chefia"}))
"""Usuária pública do grupo `chefia`."""

CAIO_KEY = Principal(subject="user:caio", scheme="api_key", groups=frozenset({"operadores"}))
"""Operador pela superfície privada, no grupo de administração das suítes."""

CAIO_OIDC = Principal(subject="user:caio", scheme="oidc")
"""O mesmo subject, pela superfície pública."""

SVC = Principal(subject="svc:ingestor", scheme="api_key")

PRINCIPALS: tuple[Principal, ...] = (ANA, BIA, CAIO_KEY, CAIO_OIDC, SVC)


# ---------------------------------------------------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------------------------------------------------


def assistant(**overrides: Any) -> dict[str, Any]:
    """Assistant público, com um pack e allowlist `ollama/*`. `campo=None` remove o campo."""
    body: dict[str, Any] = {
        "visibility": "public",
        "auth": {"schemes": ["oidc", "api_key"], "allow": ["*"]},
        "packs": ["generic"],
        "models": {"generation": "ollama/qwen3:1.7b", "allow": ["ollama/*"]},
    }
    for key, value in overrides.items():
        if value is None:
            body.pop(key, None)
        else:
            body[key] = value
    return body


def private(
    allow: Sequence[str] = ("user:caio",), schemes: Sequence[str] = ("api_key",), **overrides: Any
) -> dict[str, Any]:
    """Assistant privado que só aceita os seletores dados."""
    return assistant(visibility="private", auth={"schemes": list(schemes), "allow": list(allow)}, **overrides)


def policy(match: str = "*", **overrides: Any) -> dict[str, Any]:
    """Política de usuário: pack `generic`, flow `chat`, modelos `ollama/*`, `rpm` até 10."""
    body: dict[str, Any] = {
        "match": match,
        "packs": ["generic"],
        "flows": ["chat"],
        "models": {"allow": ["ollama/*"]},
        "limits": {"rpm": 10, "max_iterations": 3, "max_context_tokens": 4000},
    }
    body.update(overrides)
    return body


def config(
    assistants: Mapping[str, Any] | None = None,
    *,
    policies: Sequence[Mapping[str, Any]] | None = None,
    admin_group: str | None = "operadores",
) -> dict[str, Any]:
    """O mapeamento de um `assistants.yaml`."""
    data: dict[str, Any] = {"assistants": dict(assistants or {})}
    if policies is not None:
        data["user_assistants"] = {"policies": list(policies)}
    if admin_group is not None:
        data["api_keys"] = {"admin_group": admin_group}
    return data


# ---------------------------------------------------------------------------------------------------------------------
# Pack Registry falso (002)
# ---------------------------------------------------------------------------------------------------------------------


def pack_entry(
    name: str,
    *,
    status: PackStatus = PackStatus.ENABLED,
    preferred_flow: str | None = None,
    error: str | None = None,
    tools: Sequence[str] = (),
    retrievers: Sequence[str] = (),
) -> PackEntry:
    capabilities = PackCapabilities(
        system_prompt=True,
        tools=tuple(tools),
        retrievers=tuple(RetrieverCapability(name=name, collections=frozenset({"docs"})) for name in retrievers),
        reranker=False,
        validators=(),
        preferred_flow=preferred_flow,
        depends_on=(),
        requires_collections=(),
    )
    return PackEntry(
        name=name,
        version="1.0.0",
        contract_version="0.1",
        origin="code",
        status=status,
        error=error if status is not PackStatus.ENABLED else None,
        capabilities=capabilities if status is PackStatus.ENABLED else None,
    )


class FakePackRegistry:
    """Cumpre o `PackRegistry` da 002: compõe só packs habilitados, sem repetição."""

    def __init__(self, *entries: PackEntry) -> None:
        self._entries = {entry.name: entry for entry in entries}

    def entries(self) -> Sequence[PackEntry]:
        return sorted(self._entries.values(), key=lambda entry: entry.name)

    def entry(self, name: str) -> PackEntry | None:
        return self._entries.get(name)

    def compose(self, pack_names: Sequence[str]) -> Composition:
        if len(set(pack_names)) != len(pack_names):
            raise CompositionError("pack repetido na composição", packs=pack_names)
        for name in pack_names:
            entry = self._entries.get(name)
            if entry is None:
                raise CompositionError(f"pack '{name}' não está instalado", packs=pack_names)
            if entry.status is not PackStatus.ENABLED:
                raise CompositionError(
                    f"pack '{name}' não está habilitado: {entry.error or entry.status}", packs=pack_names
                )
        return Composition(packs=tuple(pack_names))


def default_registry() -> FakePackRegistry:
    """`generic` (sem flow preferido; tools `calculate` e `buscar`, como as referências com namespace da Fase 3 pedem),
    `rag` (prefere `agentic`), `financeiro` (em erro)."""
    return FakePackRegistry(
        pack_entry("generic", tools=("calculate", "buscar")),
        pack_entry("rag", preferred_flow="agentic"),
        pack_entry("financeiro", status=PackStatus.ERROR, error="contrato incompatível"),
    )


# ---------------------------------------------------------------------------------------------------------------------
# Relógio
# ---------------------------------------------------------------------------------------------------------------------


class MutableClock:
    """Relógio que só anda quando a suíte manda."""

    def __init__(self, at: datetime = T0) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at

    def advance(self, seconds: float) -> None:
        self._at += timedelta(seconds=seconds)


# ---------------------------------------------------------------------------------------------------------------------
# JWT e JWKS
# ---------------------------------------------------------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@dataclass
class SigningKey:
    """Par de chaves de teste, com o `kid` e o algoritmo que o JWKS anuncia."""

    kid: str
    alg: str
    private: Any
    public: Any

    @classmethod
    def rsa(cls, kid: str = "rsa-1") -> SigningKey:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        return cls(kid=kid, alg="RS256", private=key, public=key.public_key())

    @classmethod
    def ec(cls, kid: str = "ec-1") -> SigningKey:
        key = ec.generate_private_key(ec.SECP256R1())
        return cls(kid=kid, alg="ES256", private=key, public=key.public_key())

    def jwk(self) -> dict[str, Any]:
        algorithm = RSAAlgorithm if self.alg.startswith("RS") else ECAlgorithm
        data: dict[str, Any] = dict(algorithm.to_jwk(self.public, as_dict=True))
        data.update({"kid": self.kid, "alg": self.alg, "use": "sig"})
        return data

    def public_pem(self) -> bytes:
        return bytes(
            self.public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        )

    def sign(self, claims: Mapping[str, Any], *, kid: str | None = None) -> str:
        return jwt.encode(dict(claims), self.private, algorithm=self.alg, headers={"kid": kid or self.kid})


def claims(sub: str = "ana", *, at: datetime = T0, ttl: int = 300, **extra: Any) -> dict[str, Any]:
    """Claims válidas no instante `at`."""
    body: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": sub,
        "iat": int(at.timestamp()),
        "exp": int((at + timedelta(seconds=ttl)).timestamp()),
    }
    body.update(extra)
    return body


def forge(header: Mapping[str, Any], payload: Mapping[str, Any], *, hmac_secret: bytes | None = None) -> str:
    """Token montado à mão — para `alg: none` e HS256 assinado com a chave pública (confusão de algoritmo)."""
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}"
    signature = b""
    if hmac_secret is not None:
        signature = hmac.new(hmac_secret, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


@dataclass
class JwksServer:
    """Provedor OIDC falso servido por `httpx.MockTransport`: descoberta e JWKS, contando as buscas."""

    keys: list[SigningKey]
    jwks_fetches: int = 0
    requests: list[str] = field(default_factory=list)
    extra: list[dict[str, Any]] = field(default_factory=list)
    """Entradas cruas a mais no JWKS (ex.: a chave de cifragem que o Keycloak sempre publica)."""

    @property
    def jwks_url(self) -> str:
        return f"{ISSUER}/jwks"

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if url == f"{ISSUER}/.well-known/openid-configuration":
            return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": self.jwks_url})
        if url == self.jwks_url:
            self.jwks_fetches += 1
            return httpx.Response(200, json={"keys": [*self.extra, *(key.jwk() for key in self.keys)]})
        return httpx.Response(404)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


# ---------------------------------------------------------------------------------------------------------------------
# Serviços montados com adapters em memória
# ---------------------------------------------------------------------------------------------------------------------


def assistants_service(
    data: Mapping[str, Any],
    *,
    packs: FakePackRegistry | None = None,
    flows: frozenset[str] = FLOWS,
    clock: MutableClock | None = None,
    users: Any = None,
    mcp: Any = None,
    collections: Any = None,
    rate: Any = None,
    flow_roles: Any = None,
    overrides: Any = None,
) -> Any:
    """`AssistantsService` com os adapters em memória, a partir do mapeamento de um `assistants.yaml`."""
    from ai_core.assistants.adapters.catalogs import EmptyCollectionCatalog, EmptyMcpDirectory
    from ai_core.assistants.adapters.memory import InMemoryAssistantConfigSource, InMemoryUserAssistantStore
    from ai_core.assistants.adapters.rate_memory import InMemoryRateCounterStore
    from ai_core.assistants.service import AssistantsService

    return AssistantsService(
        config=InMemoryAssistantConfigSource(data).load(),
        packs=packs or default_registry(),
        flows=flows,
        users=users if users is not None else InMemoryUserAssistantStore(),
        mcp=mcp if mcp is not None else EmptyMcpDirectory(),
        collections=collections if collections is not None else EmptyCollectionCatalog(),
        rate=rate if rate is not None else InMemoryRateCounterStore(),
        clock=clock or MutableClock(),
        flow_roles=flow_roles,
        overrides=overrides,
    )


def access_service(
    *,
    keys: Any = None,
    oidc: Any = None,
    clock: MutableClock | None = None,
    admin_group: str | None = "operadores",
    tokens: Any = None,
) -> Any:
    """`AccessService` com os adapters em memória."""
    from ai_core.assistants.adapters.memory import (
        DisabledOidcVerifier,
        InMemoryApiKeyStore,
        SequentialTokenGenerator,
    )
    from ai_core.assistants.domain.access import OidcClaims
    from ai_core.assistants.service import AccessService

    return AccessService(
        keys=keys if keys is not None else InMemoryApiKeyStore(),
        oidc=oidc if oidc is not None else DisabledOidcVerifier(),
        tokens=tokens if tokens is not None else SequentialTokenGenerator(),
        clock=clock or MutableClock(),
        claims=OidcClaims(),
        admin_group=admin_group,
    )


Factory = Callable[[], Any]


# ---------------------------------------------------------------------------------------------------------------------
# Assistants de usuário
# ---------------------------------------------------------------------------------------------------------------------


def draft(name: str = "meu-rag", **overrides: Any) -> Any:
    """Rascunho dentro da política default das suítes: pack `generic`, modelo `ollama/qwen3:1.7b`."""
    from ai_core.assistants.api import DraftLimits, UserAssistantDraft
    from ai_core.llm.api import ModelRef

    fields: dict[str, Any] = {
        "name": name,
        "packs": ("generic",),
        "models": {"generation": ModelRef.parse("ollama/qwen3:1.7b")},
    }
    if "limits" in overrides and isinstance(overrides["limits"], Mapping):
        overrides["limits"] = DraftLimits(**overrides["limits"])
    if "models" in overrides:
        overrides["models"] = {role: ModelRef.parse(ref) for role, ref in overrides["models"].items()}
    fields.update(overrides)
    return UserAssistantDraft(**fields)


POLICIES = [
    policy(
        match="group:chefia",
        packs=["generic", "rag"],
        flows=["chat", "agentic"],
        collections=["docs"],
        models={"allow": ["ollama/*", "openai/*"]},
        limits={"rpm": 30, "max_iterations": 6, "max_context_tokens": 8000},
        write_tools=True,
    ),
    policy(match="*"),
]
"""`chefia` pode mais (openai, rag, coleções, escrita); o resto, o default de `policy()`."""
