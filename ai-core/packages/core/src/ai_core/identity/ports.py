"""Portas secundárias da 012 (specs/012-core-identity/contracts/ports.md).

Cada porta existe por I/O, não-determinismo ou algo lento cuja troca deixa as suítes ágeis (princípio XIII). Nenhum tipo
de biblioteca de infraestrutura aparece aqui. Os registros que passam por elas moram em `domain/records.py`, porque as
regras puras também os leem.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime
from typing import Protocol

from ai_core.identity.domain.records import (
    AccountRecord,
    AuthorizationCode,
    BootstrapAdmin,
    Client,
    CodeUse,
    GeneratedKey,
    GoogleClient,
    GoogleIdentity,
    IdentitySettings,
    KeyState,
    PendingAuthorization,
    RefreshStatus,
    RefreshToken,
    Session,
    SigningKey,
)

__all__ = [
    "AccountRecord",
    "AuthorizationCode",
    "BootstrapAdmin",
    "Client",
    "CodeUse",
    "GeneratedKey",
    "GoogleClient",
    "GoogleIdentity",
    "IdentitySettings",
    "KeyState",
    "PendingAuthorization",
    "RefreshStatus",
    "RefreshToken",
    "Session",
    "SigningKey",
]

# ---------------------------------------------------------------------------------------------------------------------
# Erros das portas
# ---------------------------------------------------------------------------------------------------------------------


class SealError(Exception):
    """Selo que não abre: chave mestra errada ou dado adulterado. A mensagem nunca traz o conteúdo."""


class UpstreamError(Exception):
    """Falha ao falar com o Google: rede, resposta ou `id_token` inválido."""


class SecretsError(ValueError):
    """Configuração de segredo incompleta; a mensagem nomeia a variável, nunca um valor."""


# ---------------------------------------------------------------------------------------------------------------------
# Armazenamentos
# ---------------------------------------------------------------------------------------------------------------------


class AccountStore(Protocol):
    """Contas, grupos e membros. Nome e e-mail únicos entre todas as contas (ativas ou não), sem diferenciar caixa."""

    async def get(self, account_id: str) -> AccountRecord | None: ...

    async def by_username(self, username: str) -> AccountRecord | None: ...

    async def by_email(self, email: str) -> AccountRecord | None: ...

    async def by_google_sub(self, sub: str) -> AccountRecord | None: ...

    async def list(
        self, *, query: str | None, active: bool | None, limit: int, after: str | None
    ) -> tuple[AccountRecord, ...]:
        """Por nome de usuário, a partir do nome seguinte a `after`; `query` busca em usuário, e-mail e nome."""
        ...

    async def count(self) -> int: ...

    async def insert(self, record: AccountRecord) -> None:
        """`Conflict("username" | "email" | "google_sub")` se já em uso; `GroupNotFound` para grupo inexistente."""
        ...

    async def replace(self, record: AccountRecord, *, expected_version: int) -> None:
        """Grava se a versão guardada é `expected_version`; senão `Conflict("version")`. Também `Conflict` de e-mail."""
        ...

    async def groups(self) -> Mapping[str, int]:
        """Grupos existentes → quantas contas **ativas** os integram."""
        ...

    async def add_group(self, name: str, *, at: datetime) -> None:
        """`Conflict("name")` se já existe."""
        ...

    async def remove_group(self, name: str, *, at: datetime, actor: str) -> bool:
        """Apaga o grupo e as associações; as contas afetadas sobem de versão. `False` se não existe."""
        ...

    async def set_members(self, name: str, account_ids: Collection[str], *, at: datetime, actor: str) -> None:
        """Membros exatamente estes; só as contas que mudaram sobem de versão. `GroupNotFound` se não existe."""
        ...

    async def active_members(self, name: str) -> frozenset[str]:
        """Ids das contas ativas no grupo."""
        ...


class GrantStore(Protocol):
    """Pedidos pendentes, códigos, sessões e renovação — tudo por hash. Revogar uma sessão revoga a renovação dela."""

    async def put_pending(self, pending: PendingAuthorization) -> None: ...

    async def get_pending(self, id_hash: str) -> PendingAuthorization | None: ...

    async def pending_by_google_state(self, state_hash: str) -> PendingAuthorization | None: ...

    async def replace_pending(self, pending: PendingAuthorization) -> None: ...

    async def take_pending(self, id_hash: str) -> PendingAuthorization | None:
        """Remove e devolve numa operação só: dois logins simultâneos não tiram dois códigos do mesmo pedido."""
        ...

    async def put_code(self, code: AuthorizationCode) -> None: ...

    async def consume_code(self, hash: str, *, at: datetime) -> CodeUse | None:
        """Marca o uso atomicamente; uma segunda troca devolve `reused=True` (FR-007)."""
        ...

    async def create_session(self, session: Session) -> None: ...

    async def get_session(self, id_hash: str) -> Session | None: ...

    async def revoke_session(self, id_hash: str, *, at: datetime) -> None: ...

    async def revoke_account_sessions(self, account_id: str, *, at: datetime, keep: str | None = None) -> None:
        """Todas as sessões da conta, menos `keep`, e a renovação delas."""
        ...

    async def revoke_all_sessions(self, *, at: datetime) -> None: ...

    async def put_refresh(self, token: RefreshToken) -> None: ...

    async def get_refresh(self, hash: str) -> RefreshToken | None: ...

    async def rotate_refresh(self, old_hash: str, new: RefreshToken) -> bool:
        """`active` → `rotated` e grava `new`, numa operação só; `False` se `old_hash` já não estava ativo."""
        ...

    async def revoke_family(self, family_id: str) -> None: ...

    async def purge(self, *, now: datetime, codes_before: datetime) -> int:
        """Apaga pedidos vencidos, códigos vencidos antes de `codes_before` (o reuso de um código recente ainda revoga a
        família), sessões vencidas ou revogadas e a renovação delas; devolve quantos registros saíram."""
        ...


class SigningKeyStore(Protocol):
    async def all(self) -> tuple[SigningKey, ...]:
        """Em ordem de criação."""
        ...

    async def put(self, key: SigningKey) -> None: ...

    async def set_state(self, kid: str, state: KeyState, *, at: datetime) -> None:
        """`retiring` grava `retiring_since = at`."""
        ...


class IdentitySettingsStore(Protocol):
    async def get(self) -> IdentitySettings:
        """Sem gravação ainda: `IdentitySettings()` (versão 0)."""
        ...

    async def put(self, settings: IdentitySettings, *, expected_version: int) -> bool:
        """`False` se a versão guardada não é `expected_version`."""
        ...


class LoginAttempts(Protocol):
    """Contadores de falha por chave (usuário normalizado, origem). Processo único (R11)."""

    def blocked(self, keys: Collection[str], *, now: datetime) -> bool: ...

    def fail(self, keys: Collection[str], *, now: datetime) -> None: ...

    def reset(self, keys: Collection[str]) -> None: ...


# ---------------------------------------------------------------------------------------------------------------------
# Criptografia, rede, arquivo, segredos, tempo e aleatoriedade
# ---------------------------------------------------------------------------------------------------------------------


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...

    async def verify(self, password_hash: str, password: str) -> bool:
        """Nunca levanta: hash malformado = `False`."""
        ...

    def needs_rehash(self, password_hash: str) -> bool: ...

    async def dummy_verify(self, password: str) -> None:
        """Mesmo custo de uma verificação real — para quem não existe (FR-003)."""
        ...


class TokenSigner(Protocol):
    def generate_key(self) -> GeneratedKey: ...

    def sign(self, claims: Mapping[str, object], *, kid: str, private_pem: bytes) -> str:
        """JWT RS256 com `kid` no cabeçalho."""
        ...

    def verify(self, token: str, jwks: Mapping[str, object]) -> Mapping[str, object] | None:
        """Só a assinatura RS256 contra o `kid`; tempo, emissor e audiência são do domínio. Nunca levanta."""
        ...


class SecretCipher(Protocol):
    def seal(self, plaintext: bytes) -> bytes: ...

    def open(self, sealed: bytes) -> bytes:
        """`SealError` se não abre."""
        ...


class UpstreamOidc(Protocol):
    """O provedor Google, como cliente OIDC."""

    async def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str: ...

    async def exchange(self, *, code: str, code_verifier: str) -> GoogleIdentity:
        """Troca o código e verifica o `id_token` (assinatura, `iss`, `aud`); `UpstreamError` em qualquer falha."""
        ...


class ClientSource(Protocol):
    def load(self) -> tuple[Client, ...]:
        """`ClientsFileError` nomeando o campo."""
        ...


class IdentitySecrets(Protocol):
    """Segredos e ajustes da instalação, por nomes fixos (ADR-020)."""

    def client_secret(self, ref: str) -> str | None: ...

    def google(self) -> GoogleClient | None: ...

    def google_login(self) -> bool | None:
        """`AI_CORE_GOOGLE_LOGIN`; ausente = a administração decide (ADR-033)."""
        ...

    def bootstrap_admin(self) -> BootstrapAdmin | None:
        """`SecretsError` nomeando a variável quando o conjunto está incompleto ou o arquivo falta."""
        ...


class Clock(Protocol):
    """Tempo (ADR-013). A 011 injeta o mesmo relógio em todos os módulos."""

    def now(self) -> datetime:
        """Instante atual, sempre com timezone."""
        ...


class TokenGenerator(Protocol):
    """Aleatoriedade: tokens opacos, ids e senhas temporárias."""

    def token(self, nbytes: int = 32) -> str:
        """Texto seguro para URL com `nbytes` de entropia."""
        ...

    def uuid(self) -> str: ...

    def password(self) -> str:
        """Senha temporária: 20 caracteres sem ambíguos, em grupos de 4 com hífen (R10)."""
        ...
