"""A identidade da plataforma (012) na composition root: portas por perfil, montagem do serviço e a etapa `identity`
(research R36 a R39, R42).

A 012 só existe com `AXON_IDENTITY_ENABLED`. A etapa roda depois de `adapters` e antes de `assistants`: o
verificador OIDC da 003 passa a ler as chaves do seam `PublicKeySet` em processo (`CallableJwksSource`), sem a
plataforma chamar a si mesma pela rede (ADR-030). No `persistent`, o boot inicia a identidade numa sessão de
armazenamento própria (chave de assinatura, admin inicial) e o serviço de runtime carrega as chaves no início do ciclo
de vida da app, quando o pool de serviço abre (R13).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import httpx

from axon_ai.assistants.adapters.oidc import CallableJwksSource, JwksOidcVerifier
from axon_ai.bootstrap.settings import TEST_PROFILE, ConfigurationError, Settings
from axon_ai.identity.adapters.cipher import AesGcmCipher
from axon_ai.identity.adapters.clients_yaml import YamlClientSource
from axon_ai.identity.adapters.google import GoogleOidc
from axon_ai.identity.adapters.http import IdentityHttpSettings
from axon_ai.identity.adapters.memory import (
    InMemoryAccountStore,
    InMemoryClientSource,
    InMemoryGrantStore,
    InMemoryIdentitySecrets,
    InMemoryIdentitySettingsStore,
    InMemoryLoginAttempts,
    InMemorySigningKeyStore,
    SimulatedUpstreamOidc,
)
from axon_ai.identity.adapters.passwords import Argon2PasswordHasher
from axon_ai.identity.adapters.postgres import (
    PostgresAccountStore,
    PostgresGrantStore,
    PostgresIdentitySettingsStore,
    PostgresSigningKeyStore,
)
from axon_ai.identity.adapters.secrets_env import EnvironmentIdentitySecrets
from axon_ai.identity.adapters.signing import RsaTokenSigner
from axon_ai.identity.adapters.system import SystemTokenGenerator
from axon_ai.identity.ports import BootstrapAdmin, Client, GoogleClient
from axon_ai.identity.service import IdentityConfig, IdentityService

logger: Final = logging.getLogger("axon_ai.bootstrap")

DEFAULT_ADMIN_GROUP: Final = "admin"
"""Grupo protegido da 012 quando o `assistants.yaml` não declara `api_keys.admin_group`."""

IDENTITY_PURGE_INTERVAL: Final = 3600.0
"""Expurgo de pedidos, códigos, sessões e chaves vencidos (012 R12): a cada hora."""

# --- credenciais do perfil `test` com a identidade ligada, exportadas para as suítes (R39) ---------------------------

TEST_ADMIN_USERNAME: Final = "admin-teste"
TEST_ADMIN_PASSWORD: Final = "senha-do-admin-de-teste"
TEST_MASTER_KEY: Final = bytes(range(32))
TEST_CHAT_CLIENT: Final = "open-webui"
TEST_CHAT_SECRET: Final = "segredo-do-cliente-de-teste"
TEST_CHAT_CALLBACK: Final = "http://localhost:3000/oauth/oidc/callback"
TEST_CONSOLE_CLIENT: Final = "console"
TEST_CONSOLE_CALLBACK: Final = "http://localhost:8080/callback"
TEST_GOOGLE: Final = GoogleClient(client_id="cliente-google-de-teste", client_secret="segredo-google-de-teste")

TEST_CLIENTS: Final = (
    Client(
        id=TEST_CHAT_CLIENT,
        type="confidential",
        audience="axon",
        redirect_uris=(TEST_CHAT_CALLBACK,),
        post_logout_redirect_uris=("http://localhost:3000/auth",),
        secret_ref="open_webui",
    ),
    Client(
        id=TEST_CONSOLE_CLIENT,
        type="public",
        audience="axon-admin",
        redirect_uris=(TEST_CONSOLE_CALLBACK,),
        post_logout_redirect_uris=("http://localhost:8080/",),
    ),
)
"""Os dois clientes do `identity.yaml` de exemplo; o `test` os usa quando não há arquivo de clientes."""


# --- fábricas das portas (R38) ----------------------------------------------------------------------------------------


def memory_identity_ports() -> dict[str, Any]:
    """Armazenamentos e contadores em memória: `memory` e `test`."""
    return {
        "identity_accounts": lambda _s, _p: InMemoryAccountStore(),
        "identity_grants": lambda _s, _p: InMemoryGrantStore(),
        "identity_keys": lambda _s, _p: InMemorySigningKeyStore(),
        "identity_settings": lambda _s, _p: InMemoryIdentitySettingsStore(),
        "identity_attempts": lambda _s, _p: InMemoryLoginAttempts(),
    }


def postgres_identity_ports() -> dict[str, Any]:
    """Schema `identity` no `persistent` (ADR-015); os contadores ficam em memória (processo único, 012 R11)."""
    return {
        "identity_accounts": lambda _s, p: PostgresAccountStore(p["database"]),
        "identity_grants": lambda _s, p: PostgresGrantStore(p["database"]),
        "identity_keys": lambda _s, p: PostgresSigningKeyStore(p["database"]),
        "identity_settings": lambda _s, p: PostgresIdentitySettingsStore(p["database"]),
        "identity_attempts": lambda _s, _p: InMemoryLoginAttempts(),
    }


def env_identity_secrets(_settings: Settings, _parts: Mapping[str, Any]) -> Any:
    return EnvironmentIdentitySecrets()


def seeded_identity_secrets(_settings: Settings, _parts: Mapping[str, Any]) -> Any:
    """Segredo do cliente do chat, um Google simulado e o admin semeado (R39)."""
    return InMemoryIdentitySecrets(
        client_secrets={"open_webui": TEST_CHAT_SECRET},
        google=TEST_GOOGLE,
        bootstrap_admin=BootstrapAdmin(
            username=TEST_ADMIN_USERNAME, email=f"{TEST_ADMIN_USERNAME}@exemplo.test", password=TEST_ADMIN_PASSWORD
        ),
    )


def google_upstream(settings: Settings, parts: Mapping[str, Any]) -> Any:
    """O Google real, só com a identidade ligada e o cliente configurado na instalação; senão, nenhum."""
    if not settings.identity_enabled or settings.public_url is None:
        return None
    client = parts["identity_secrets"].google()
    if client is None:
        return None
    return GoogleOidc(
        client=client,
        redirect_uri=f"{settings.public_url.rstrip('/')}/oauth2/google/callback",
        http=httpx.AsyncClient(timeout=10.0),
        clock=parts["clock"],
    )


def simulated_upstream(_settings: Settings, _parts: Mapping[str, Any]) -> Any:
    return SimulatedUpstreamOidc()


# --- serviço ----------------------------------------------------------------------------------------------------------


def admin_group(parts: Mapping[str, Any]) -> str:
    return getattr(parts.get("assistants_config"), "admin_group", None) or DEFAULT_ADMIN_GROUP


def master_key(settings: Settings) -> bytes:
    """A do ambiente; no `test`, a fixa; no `memory` sem ela, uma aleatória por processo (as sessões não sobrevivem a
    um restart — o mesmo que já acontece com tudo no `memory`)."""
    if settings.master_key is not None:
        return settings.master_key
    if settings.profile == TEST_PROFILE:
        return TEST_MASTER_KEY
    logger.warning("AXON_MASTER_KEY ausente: chave mestra aleatória neste processo (perfil '%s')", settings.profile)
    return os.urandom(32)


def shared_master_key(parts: dict[str, Any]) -> bytes:
    """Uma chave mestra por processo para todos os módulos que selam segredos (012, 009): no `memory` sem a variável,
    a aleatória é sorteada uma vez só (ADR-033; cada módulo deriva a própria subchave)."""
    key = parts.get("master_key")
    if key is None:
        key = master_key(parts["settings"])
        parts["master_key"] = key
    return key


def client_source(settings: Settings) -> Any:
    if settings.identity_clients_file is not None:
        return YamlClientSource(settings.identity_clients_file)
    return InMemoryClientSource(TEST_CLIENTS)


def identity_service(parts: Mapping[str, Any], *, session: Mapping[str, Any]) -> IdentityService:
    """A 012 sobre os armazenamentos de `session`: os da plataforma na API, os de uma sessão própria no boot e na
    linha de comando (R13). As partes sem estado (hash, assinatura, cifra) são as da plataforma."""
    settings: Settings = parts["settings"]
    if settings.public_url is None:  # pragma: no cover — a configuração já recusou
        raise ConfigurationError("AXON_PUBLIC_URL: obrigatório com AXON_IDENTITY_ENABLED")
    return IdentityService(
        config=IdentityConfig(public_url=settings.public_url, admin_group=admin_group(parts)),
        accounts=session["identity_accounts"],
        grants=session["identity_grants"],
        keys=session["identity_keys"],
        settings=session["identity_settings"],
        attempts=parts["identity_attempts"],
        hasher=parts["identity_hasher"],
        signer=parts["identity_signer"],
        cipher=parts["identity_cipher"],
        clients=client_source(settings),
        secrets=parts["identity_secrets"],
        clock=parts["clock"],
        tokens=SystemTokenGenerator(),
        google=parts["identity_upstream"],
    )


def prepare(parts: dict[str, Any]) -> None:
    """As partes sem estado da 012, uma vez por processo: o hash fictício do argon2 custa um cálculo inteiro."""
    parts.setdefault("identity_hasher", Argon2PasswordHasher())
    parts.setdefault("identity_signer", RsaTokenSigner())
    parts.setdefault("identity_cipher", AesGcmCipher(shared_master_key(parts)))


def verifier(service: IdentityService) -> JwksOidcVerifier:
    """O verificador da 003 com as chaves do emissor da plataforma, em processo (003 R26)."""
    return JwksOidcVerifier(issuer=service.config.issuer, source=CallableJwksSource(service.jwks))


def http_settings(settings: Settings) -> IdentityHttpSettings:
    """Marca da instalação, cookie e proxies para as páginas e o protocolo (012 FR-023, R5, R8)."""
    return IdentityHttpSettings(
        display_name=settings.display_name,
        logo=_logo(settings.logo_file),
        cookie_secure=settings.secure_cookie,
        trusted_proxies=settings.trusted_proxies,
    )


_LOGO_TYPES: Final = {".svg": "image/svg+xml", ".png": "image/png"}


def _logo(path: Path | None) -> tuple[bytes, str] | None:
    if path is None:
        return None
    media_type = _LOGO_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ConfigurationError("AXON_LOGO_FILE: precisa ser SVG ou PNG")
    try:
        return path.read_bytes(), media_type
    except OSError as error:
        raise ConfigurationError(f"AXON_LOGO_FILE: não foi possível ler o arquivo ({error.strerror})") from None
