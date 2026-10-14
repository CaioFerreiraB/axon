"""Adapters em memória e de teste das portas da 012 (contracts/ports.md).

São o adapter em memória que o princípio XIII exige de cada porta e o que os perfis `memory` e `test` da composition
root usam. Moram na distribuição, não no kit de teste, pelo mesmo motivo dos da 003: a suíte de um pack externo sobe a
plataforma de verdade com eles. O `SecretCipher` e o `TokenSigner` não têm versão de memória: os reais, com chave fixa
ou pequena, já são rápidos e determinísticos o bastante.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Callable, Collection, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Final
from urllib.parse import urlencode

from ai_core.identity.api import Conflict, GroupNotFound
from ai_core.identity.domain.accounts import PASSWORD_ALPHABET, group_password
from ai_core.identity.domain.attempts import AttemptPolicy, AttemptState, is_blocked, is_idle, register_failure
from ai_core.identity.domain.pkce import s256
from ai_core.identity.domain.records import (
    AccountRecord,
    AuthorizationCode,
    BootstrapAdmin,
    Client,
    CodeUse,
    GoogleClient,
    GoogleIdentity,
    IdentitySettings,
    KeyState,
    PendingAuthorization,
    RefreshToken,
    Session,
    SigningKey,
)
from ai_core.identity.ports import UpstreamError

# ---------------------------------------------------------------------------------------------------------------------
# Armazenamentos
# ---------------------------------------------------------------------------------------------------------------------


class InMemoryAccountStore:
    """Contas por id; grupos por nome. Os membros moram em `Account.groups`, como o Postgres os devolve."""

    def __init__(self) -> None:
        self._accounts: dict[str, AccountRecord] = {}
        self._groups: dict[str, datetime] = {}

    async def get(self, account_id: str) -> AccountRecord | None:
        return self._accounts.get(account_id)

    async def by_username(self, username: str) -> AccountRecord | None:
        return self._find(lambda record: record.account.username == username.lower())

    async def by_email(self, email: str) -> AccountRecord | None:
        return self._find(lambda record: record.account.email == email.lower())

    async def by_google_sub(self, sub: str) -> AccountRecord | None:
        return self._find(lambda record: record.google_sub == sub)

    async def list(
        self, *, query: str | None, active: bool | None, limit: int, after: str | None
    ) -> tuple[AccountRecord, ...]:
        needle = (query or "").strip().lower()
        found = sorted(
            (
                record
                for record in self._accounts.values()
                if (active is None or record.account.active == active)
                and (after is None or record.account.username > after)
                and (
                    not needle
                    or needle in record.account.username
                    or needle in record.account.email
                    or needle in record.account.name.lower()
                )
            ),
            key=lambda record: record.account.username,
        )
        return tuple(found[:limit])

    async def count(self) -> int:
        return len(self._accounts)

    async def insert(self, record: AccountRecord) -> None:
        self._check_unique(record, ignore=None)
        self._check_groups(record.account.groups)
        self._accounts[record.account.id] = record

    async def replace(self, record: AccountRecord, *, expected_version: int) -> None:
        current = self._accounts.get(record.account.id)
        if current is None or current.account.version != expected_version:
            raise Conflict(
                "a conta mudou desde a leitura",
                field="version",
                current_version=current.account.version if current else None,
            )
        self._check_unique(record, ignore=record.account.id)
        self._check_groups(record.account.groups)
        self._accounts[record.account.id] = record

    async def groups(self) -> Mapping[str, int]:
        counts = dict.fromkeys(self._groups, 0)
        for record in self._accounts.values():
            if record.account.active:
                for group in record.account.groups:
                    counts[group] += 1
        return dict(sorted(counts.items()))

    async def add_group(self, name: str, *, at: datetime) -> None:
        if name in self._groups:
            raise Conflict(f"o grupo {name!r} já existe", field="name")
        self._groups[name] = at

    async def remove_group(self, name: str, *, at: datetime, actor: str) -> bool:
        if name not in self._groups:
            return False
        del self._groups[name]
        for record in list(self._accounts.values()):
            if name in record.account.groups:
                self._bump(record, groups=record.account.groups - {name}, at=at, actor=actor)
        return True

    async def set_members(self, name: str, account_ids: Collection[str], *, at: datetime, actor: str) -> None:
        if name not in self._groups:
            raise GroupNotFound(f"o grupo {name!r} não existe")
        wanted = set(account_ids)
        unknown = wanted - set(self._accounts)
        if unknown:
            raise ValueError(f"contas inexistentes: {sorted(unknown)}")
        for record in list(self._accounts.values()):
            inside = name in record.account.groups
            if record.account.id in wanted and not inside:
                self._bump(record, groups=record.account.groups | {name}, at=at, actor=actor)
            elif record.account.id not in wanted and inside:
                self._bump(record, groups=record.account.groups - {name}, at=at, actor=actor)

    async def active_members(self, name: str) -> frozenset[str]:
        return frozenset(
            record.account.id
            for record in self._accounts.values()
            if record.account.active and name in record.account.groups
        )

    def _find(self, predicate: Callable[[AccountRecord], bool]) -> AccountRecord | None:
        return next((record for record in self._accounts.values() if predicate(record)), None)

    def _check_unique(self, record: AccountRecord, *, ignore: str | None) -> None:
        for other in self._accounts.values():
            if other.account.id == ignore:
                continue
            if other.account.id == record.account.id:
                raise Conflict("id de conta em uso", field="id")
            if other.account.username == record.account.username:
                raise Conflict(f"o usuário {record.account.username!r} já existe", field="username")
            if other.account.email == record.account.email:
                raise Conflict("o e-mail já está em uso", field="email")
            if record.google_sub is not None and other.google_sub == record.google_sub:
                raise Conflict("a conta Google já está vinculada a outra conta", field="google_sub")

    def _check_groups(self, groups: Iterable[str]) -> None:
        missing = sorted(set(groups) - set(self._groups))
        if missing:
            raise GroupNotFound(f"o grupo {missing[0]!r} não existe")

    def _bump(self, record: AccountRecord, *, groups: frozenset[str], at: datetime, actor: str) -> None:
        account = dataclasses.replace(
            record.account, groups=groups, updated_at=at, updated_by=actor, version=record.account.version + 1
        )
        self._accounts[account.id] = dataclasses.replace(record, account=account)


class InMemoryGrantStore:
    """Pedidos, códigos, sessões e renovação em dicionários por hash."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingAuthorization] = {}
        self._codes: dict[str, AuthorizationCode] = {}
        self._sessions: dict[str, Session] = {}
        self._refresh: dict[str, RefreshToken] = {}

    async def put_pending(self, pending: PendingAuthorization) -> None:
        self._pending[pending.id_hash] = pending

    async def get_pending(self, id_hash: str) -> PendingAuthorization | None:
        return self._pending.get(id_hash)

    async def pending_by_google_state(self, state_hash: str) -> PendingAuthorization | None:
        return next((p for p in self._pending.values() if p.google_state_hash == state_hash), None)

    async def replace_pending(self, pending: PendingAuthorization) -> None:
        if pending.id_hash in self._pending:
            self._pending[pending.id_hash] = pending

    async def take_pending(self, id_hash: str) -> PendingAuthorization | None:
        return self._pending.pop(id_hash, None)

    async def put_code(self, code: AuthorizationCode) -> None:
        self._codes[code.hash] = code

    async def consume_code(self, hash: str, *, at: datetime) -> CodeUse | None:
        code = self._codes.get(hash)
        if code is None:
            return None
        if code.used_at is not None:
            return CodeUse(code=code, reused=True)
        used = dataclasses.replace(code, used_at=at)
        self._codes[hash] = used
        return CodeUse(code=used, reused=False)

    async def create_session(self, session: Session) -> None:
        self._sessions[session.id_hash] = session

    async def get_session(self, id_hash: str) -> Session | None:
        return self._sessions.get(id_hash)

    async def revoke_session(self, id_hash: str, *, at: datetime) -> None:
        session = self._sessions.get(id_hash)
        if session is not None:
            self._revoke(session, at=at)

    async def revoke_account_sessions(self, account_id: str, *, at: datetime, keep: str | None = None) -> None:
        for session in list(self._sessions.values()):
            if session.account_id == account_id and session.id_hash != keep:
                self._revoke(session, at=at)

    async def revoke_all_sessions(self, *, at: datetime) -> None:
        for session in list(self._sessions.values()):
            self._revoke(session, at=at)

    async def put_refresh(self, token: RefreshToken) -> None:
        self._refresh[token.hash] = token

    async def get_refresh(self, hash: str) -> RefreshToken | None:
        return self._refresh.get(hash)

    async def rotate_refresh(self, old_hash: str, new: RefreshToken) -> bool:
        old = self._refresh.get(old_hash)
        if old is None or old.status != "active":
            return False
        self._refresh[old_hash] = dataclasses.replace(old, status="rotated", rotated_to=new.hash)
        self._refresh[new.hash] = new
        return True

    async def revoke_family(self, family_id: str) -> None:
        for token in list(self._refresh.values()):
            if token.family_id == family_id:
                self._refresh[token.hash] = dataclasses.replace(token, status="revoked")

    async def purge(self, *, now: datetime, codes_before: datetime) -> int:
        removed = 0
        for key, pending in list(self._pending.items()):
            if pending.expires_at <= now:
                del self._pending[key]
                removed += 1
        for key, code in list(self._codes.items()):
            if code.expires_at <= codes_before:
                del self._codes[key]
                removed += 1
        dead = {
            key
            for key, session in self._sessions.items()
            if session.expires_at <= now or session.revoked_at is not None
        }
        for key in dead:
            del self._sessions[key]
            removed += 1
        for key, token in list(self._refresh.items()):
            if token.session_id in dead or token.session_id not in self._sessions:
                del self._refresh[key]
                removed += 1
        return removed

    def _revoke(self, session: Session, *, at: datetime) -> None:
        if session.revoked_at is None:
            self._sessions[session.id_hash] = dataclasses.replace(session, revoked_at=at)
        for token in list(self._refresh.values()):
            if token.session_id == session.id_hash and token.status != "revoked":
                self._refresh[token.hash] = dataclasses.replace(token, status="revoked")


class InMemorySigningKeyStore:
    def __init__(self) -> None:
        self._keys: list[SigningKey] = []

    async def all(self) -> tuple[SigningKey, ...]:
        return tuple(sorted(self._keys, key=lambda key: key.created_at))

    async def put(self, key: SigningKey) -> None:
        if any(existing.kid == key.kid for existing in self._keys):
            raise Conflict(f"a chave {key.kid!r} já existe", field="kid")
        self._keys.append(key)

    async def set_state(self, kid: str, state: KeyState, *, at: datetime) -> None:
        for index, key in enumerate(self._keys):
            if key.kid == kid:
                since = at if state == "retiring" else key.retiring_since
                self._keys[index] = dataclasses.replace(key, state=state, retiring_since=since)


class InMemoryIdentitySettingsStore:
    def __init__(self) -> None:
        self._settings = IdentitySettings()

    async def get(self) -> IdentitySettings:
        return self._settings

    async def put(self, settings: IdentitySettings, *, expected_version: int) -> bool:
        if self._settings.version != expected_version:
            return False
        self._settings = settings
        return True


class InMemoryLoginAttempts:
    """Contadores por chave, no processo (R11). Também é o adapter real: não há versão compartilhada."""

    _PRUNE_AT: Final = 10_000

    def __init__(self, policy: AttemptPolicy | None = None) -> None:
        self._policy = policy or AttemptPolicy()
        self._states: dict[str, AttemptState] = {}

    def blocked(self, keys: Collection[str], *, now: datetime) -> bool:
        return any(is_blocked(self._states.get(key, AttemptState()), now=now) for key in keys)

    def fail(self, keys: Collection[str], *, now: datetime) -> None:
        for key in keys:
            self._states[key] = register_failure(self._states.get(key, AttemptState()), now=now, policy=self._policy)
        if len(self._states) > self._PRUNE_AT:
            for key, state in list(self._states.items()):
                if is_idle(state, now=now, policy=self._policy):
                    del self._states[key]

    def reset(self, keys: Collection[str]) -> None:
        for key in keys:
            self._states.pop(key, None)


# ---------------------------------------------------------------------------------------------------------------------
# Hash, Google, arquivo, segredos, tempo e aleatoriedade
# ---------------------------------------------------------------------------------------------------------------------


class FastPasswordHasher:
    """Hash rápido e determinístico para as suítes — nunca para senha de verdade."""

    def __init__(self, scheme: str = "fast-v1") -> None:
        self._scheme = scheme
        self._dummy = self._hash("conta-inexistente")

    def _hash(self, password: str, scheme: str | None = None) -> str:
        prefix = scheme or self._scheme
        return f"{prefix}${hashlib.sha256(f'{prefix}:{password}'.encode()).hexdigest()}"

    async def hash(self, password: str) -> str:
        return self._hash(password)

    async def verify(self, password_hash: str, password: str) -> bool:
        scheme, _, _ = password_hash.partition("$")
        return bool(scheme) and self._hash(password, scheme) == password_hash

    def needs_rehash(self, password_hash: str) -> bool:
        return not password_hash.startswith(self._scheme + "$")

    async def dummy_verify(self, password: str) -> None:
        await self.verify(self._dummy, password)


class SimulatedUpstreamOidc:
    """Google simulado e programável: o teste aprova um `state` com a identidade que o Google afirmaria."""

    def __init__(self, *, authorize_url: str = "https://accounts.google.test/o/oauth2/v2/auth") -> None:
        self._authorize_url = authorize_url
        self._requests: dict[str, tuple[str, str]] = {}
        self._approved: dict[str, tuple[str, GoogleIdentity]] = {}
        self._count = 0
        self.fail_exchange = False

    async def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        self._requests[state] = (nonce, code_challenge)
        query = urlencode({"state": state, "nonce": nonce, "code_challenge": code_challenge})
        return f"{self._authorize_url}?{query}"

    def approve(
        self,
        state: str,
        *,
        sub: str,
        email: str | None,
        email_verified: bool = True,
        hosted_domain: str | None = None,
        nonce: str | None = None,
    ) -> str:
        """Devolve o código que o Google mandaria ao callback. `nonce` ausente = o do pedido, como o Google faz."""
        expected_nonce, _ = self._requests[state]
        self._count += 1
        code = f"google-code-{self._count}"
        identity = GoogleIdentity(
            sub=sub,
            email=email,
            email_verified=email_verified,
            hosted_domain=hosted_domain,
            nonce=expected_nonce if nonce is None else nonce,
        )
        self._approved[code] = (state, identity)
        return code

    async def exchange(self, *, code: str, code_verifier: str) -> GoogleIdentity:
        if self.fail_exchange:
            raise UpstreamError("o Google simulado recusou a troca")
        approved = self._approved.pop(code, None)
        if approved is None:
            raise UpstreamError("código desconhecido")
        state, identity = approved
        _, challenge = self._requests[state]
        if s256(code_verifier) != challenge:
            raise UpstreamError("PKCE não confere")
        return identity


class InMemoryClientSource:
    def __init__(self, clients: Iterable[Client] = ()) -> None:
        self._clients = tuple(clients)

    def load(self) -> tuple[Client, ...]:
        return self._clients


class InMemoryIdentitySecrets:
    def __init__(
        self,
        *,
        client_secrets: Mapping[str, str] | None = None,
        google: GoogleClient | None = None,
        google_login: bool | None = None,
        bootstrap_admin: BootstrapAdmin | None = None,
    ) -> None:
        self._client_secrets = dict(client_secrets or {})
        self._google = google
        self._google_login = google_login
        self._bootstrap = bootstrap_admin

    def client_secret(self, ref: str) -> str | None:
        return self._client_secrets.get(ref)

    def google(self) -> GoogleClient | None:
        return self._google

    def google_login(self) -> bool | None:
        return self._google_login

    def bootstrap_admin(self) -> BootstrapAdmin | None:
        return self._bootstrap


class FixedClock:
    """Relógio parado e ajustável."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 10, 14, 12, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta

    def set(self, now: datetime) -> None:
        self._now = now


class SequentialTokenGenerator:
    """Tokens previsíveis, no formato dos reais: a suíte confere o valor exato, e não só a forma."""

    def __init__(self) -> None:
        self._count = 0

    def _next(self) -> int:
        self._count += 1
        return self._count

    def token(self, nbytes: int = 32) -> str:
        length = -(-nbytes * 4 // 3)
        return f"t{self._next():0{length - 1}d}"

    def uuid(self) -> str:
        return f"00000000-0000-4000-8000-{self._next():012d}"

    def password(self) -> str:
        number, chars = self._next(), []
        for _ in range(20):
            number, index = divmod(number, len(PASSWORD_ALPHABET))
            chars.append(PASSWORD_ALPHABET[index])
        return group_password("".join(chars))
