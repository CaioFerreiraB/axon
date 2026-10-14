"""Armazenamentos da 012 em Postgres, no schema `identity` (ADR-015; research R12).

As operações que o protocolo exige atômicas são um único comando: consumir um código (`UPDATE … WHERE used_at IS NULL
RETURNING`), tirar um pedido pendente (`DELETE … RETURNING`) e trocar a renovação (`UPDATE … WHERE status = 'active'`
e o `INSERT` na mesma transação). A unicidade vem dos índices; a violação vira `Conflict` com o campo.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from typing import Any, Final

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ai_core.identity.api import Account, Conflict, GroupNotFound
from ai_core.identity.ports import (
    AccountRecord,
    AuthorizationCode,
    CodeUse,
    IdentitySettings,
    KeyState,
    PendingAuthorization,
    RefreshToken,
    Session,
    SigningKey,
)

_UNIQUE_FIELDS: Final = {
    "accounts_pkey": "id",
    "accounts_username_key": "username",
    "accounts_email_key": "email",
    "accounts_google_sub_key": "google_sub",
}

# ---------------------------------------------------------------------------------------------------------------------
# Contas
# ---------------------------------------------------------------------------------------------------------------------

_ACCOUNT_COLUMNS: Final = (
    "a.id, a.username, a.email, a.name, a.active, a.password_hash, a.temporary_password, a.google_sub, a.created_at, "
    "a.updated_at, a.updated_by, a.last_login_at, a.version, "
    "COALESCE((SELECT array_agg(m.group_name) FROM identity.memberships m WHERE m.account_id = a.id), '{}')"
)


def _account(row: Sequence[Any]) -> AccountRecord:
    (
        account_id,
        username,
        email,
        name,
        active,
        password_hash,
        temporary,
        google_sub,
        created_at,
        updated_at,
        updated_by,
        last_login_at,
        version,
        groups,
    ) = row
    account = Account(
        id=account_id,
        username=username,
        email=email,
        name=name,
        groups=frozenset(groups),
        active=active,
        temporary_password=temporary,
        has_password=password_hash is not None,
        google_linked=google_sub is not None,
        created_at=created_at,
        updated_at=updated_at,
        updated_by=updated_by,
        last_login_at=last_login_at,
        version=version,
    )
    return AccountRecord(account=account, password_hash=password_hash, google_sub=google_sub)


def _conflict(error: UniqueViolation) -> Conflict:
    field = _UNIQUE_FIELDS.get(error.diag.constraint_name or "", "unknown")
    messages = {
        "username": "o usuário já existe",
        "email": "o e-mail já está em uso",
        "google_sub": "a conta Google já está vinculada a outra conta",
    }
    return Conflict(messages.get(field, "registro em uso"), field=field)


class PostgresAccountStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def _one(self, where: str, value: object) -> AccountRecord | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_ACCOUNT_COLUMNS} FROM identity.accounts a WHERE {where}", (value,)
            )
            row = await cursor.fetchone()
        return _account(row) if row is not None else None

    async def get(self, account_id: str) -> AccountRecord | None:
        return await self._one("a.id = %s", account_id)

    async def by_username(self, username: str) -> AccountRecord | None:
        return await self._one("lower(a.username) = lower(%s)", username)

    async def by_email(self, email: str) -> AccountRecord | None:
        return await self._one("lower(a.email) = lower(%s)", email)

    async def by_google_sub(self, sub: str) -> AccountRecord | None:
        return await self._one("a.google_sub = %s", sub)

    async def list(
        self, *, query: str | None, active: bool | None, limit: int, after: str | None
    ) -> tuple[AccountRecord, ...]:
        clauses: list[str] = ["TRUE"]
        params: list[object] = []
        if active is not None:
            clauses.append("a.active = %s")
            params.append(active)
        if after is not None:
            clauses.append("a.username > %s")
            params.append(after)
        needle = (query or "").strip().lower()
        if needle:
            pattern = "%" + needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            clauses.append("(a.username LIKE %s OR a.email LIKE %s OR lower(a.name) LIKE %s)")
            params.extend([pattern, pattern, pattern])
        params.append(limit)
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_ACCOUNT_COLUMNS} FROM identity.accounts a WHERE {' AND '.join(clauses)} "
                "ORDER BY a.username LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return tuple(_account(row) for row in rows)

    async def count(self) -> int:
        async with self._pool.connection() as connection:
            cursor = await connection.execute("SELECT count(*) FROM identity.accounts")
            row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def insert(self, record: AccountRecord) -> None:
        account = record.account
        try:
            async with self._pool.connection() as connection, connection.transaction():
                await connection.execute(
                    "INSERT INTO identity.accounts (id, username, email, name, active, password_hash, "
                    "temporary_password, google_sub, created_at, updated_at, updated_by, last_login_at, version) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        account.id,
                        account.username,
                        account.email,
                        account.name,
                        account.active,
                        record.password_hash,
                        account.temporary_password,
                        record.google_sub,
                        account.created_at,
                        account.updated_at,
                        account.updated_by,
                        account.last_login_at,
                        account.version,
                    ),
                )
                await self._write_groups(connection, account.id, account.groups)
        except UniqueViolation as error:
            raise _conflict(error) from None
        except ForeignKeyViolation:
            raise GroupNotFound("um dos grupos não existe") from None

    async def replace(self, record: AccountRecord, *, expected_version: int) -> None:
        account = record.account
        try:
            async with self._pool.connection() as connection, connection.transaction():
                cursor = await connection.execute(
                    "UPDATE identity.accounts SET email = %s, name = %s, active = %s, password_hash = %s, "
                    "temporary_password = %s, google_sub = %s, updated_at = %s, updated_by = %s, last_login_at = %s, "
                    "version = %s WHERE id = %s AND version = %s",
                    (
                        account.email,
                        account.name,
                        account.active,
                        record.password_hash,
                        account.temporary_password,
                        record.google_sub,
                        account.updated_at,
                        account.updated_by,
                        account.last_login_at,
                        account.version,
                        account.id,
                        expected_version,
                    ),
                )
                if cursor.rowcount != 1:
                    current = await connection.execute(
                        "SELECT version FROM identity.accounts WHERE id = %s", (account.id,)
                    )
                    row = await current.fetchone()
                    raise Conflict(
                        "a conta mudou desde a leitura", field="version", current_version=row[0] if row else None
                    )
                await connection.execute("DELETE FROM identity.memberships WHERE account_id = %s", (account.id,))
                await self._write_groups(connection, account.id, account.groups)
        except UniqueViolation as error:
            raise _conflict(error) from None
        except ForeignKeyViolation:
            raise GroupNotFound("um dos grupos não existe") from None

    @staticmethod
    async def _write_groups(connection: Any, account_id: str, groups: Collection[str]) -> None:
        for group in sorted(groups):
            await connection.execute(
                "INSERT INTO identity.memberships (account_id, group_name) VALUES (%s, %s)", (account_id, group)
            )

    async def groups(self) -> Mapping[str, int]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT g.name, count(a.id) FROM identity.groups g "
                "LEFT JOIN identity.memberships m ON m.group_name = g.name "
                "LEFT JOIN identity.accounts a ON a.id = m.account_id AND a.active "
                "GROUP BY g.name ORDER BY g.name"
            )
            rows = await cursor.fetchall()
        return {name: int(count) for name, count in rows}

    async def add_group(self, name: str, *, at: datetime) -> None:
        try:
            async with self._pool.connection() as connection:
                await connection.execute("INSERT INTO identity.groups (name, created_at) VALUES (%s, %s)", (name, at))
        except UniqueViolation:
            raise Conflict(f"o grupo {name!r} já existe", field="name") from None

    async def remove_group(self, name: str, *, at: datetime, actor: str) -> bool:
        async with self._pool.connection() as connection, connection.transaction():
            await connection.execute(
                "UPDATE identity.accounts SET version = version + 1, updated_at = %s, updated_by = %s "
                "WHERE id IN (SELECT account_id FROM identity.memberships WHERE group_name = %s)",
                (at, actor, name),
            )
            cursor = await connection.execute("DELETE FROM identity.groups WHERE name = %s", (name,))
            return cursor.rowcount == 1

    async def set_members(self, name: str, account_ids: Collection[str], *, at: datetime, actor: str) -> None:
        wanted = sorted(set(account_ids))
        async with self._pool.connection() as connection, connection.transaction():
            cursor = await connection.execute("SELECT 1 FROM identity.groups WHERE name = %s FOR UPDATE", (name,))
            if await cursor.fetchone() is None:
                raise GroupNotFound(f"o grupo {name!r} não existe")
            cursor = await connection.execute("SELECT count(*) FROM identity.accounts WHERE id = ANY(%s)", (wanted,))
            row = await cursor.fetchone()
            if row is None or int(row[0]) != len(wanted):
                raise ValueError("contas inexistentes na lista de membros")
            cursor = await connection.execute(
                "DELETE FROM identity.memberships WHERE group_name = %s AND NOT (account_id = ANY(%s)) "
                "RETURNING account_id",
                (name, wanted),
            )
            changed = {r[0] for r in await cursor.fetchall()}
            cursor = await connection.execute(
                "INSERT INTO identity.memberships (account_id, group_name) SELECT unnest(%s::text[]), %s "
                "ON CONFLICT DO NOTHING RETURNING account_id",
                (wanted, name),
            )
            changed |= {r[0] for r in await cursor.fetchall()}
            if changed:
                await connection.execute(
                    "UPDATE identity.accounts SET version = version + 1, updated_at = %s, updated_by = %s "
                    "WHERE id = ANY(%s)",
                    (at, actor, sorted(changed)),
                )

    async def active_members(self, name: str) -> frozenset[str]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT a.id FROM identity.accounts a JOIN identity.memberships m ON m.account_id = a.id "
                "WHERE m.group_name = %s AND a.active",
                (name,),
            )
            rows = await cursor.fetchall()
        return frozenset(row[0] for row in rows)


# ---------------------------------------------------------------------------------------------------------------------
# Pedidos, códigos, sessões e renovação
# ---------------------------------------------------------------------------------------------------------------------

_PENDING_COLUMNS: Final = (
    "id_hash, csrf_hash, client_id, redirect_uri, scope, state, nonce, code_challenge, account_id, google_state_hash, "
    "google_nonce, google_verifier, created_at, expires_at"
)
_CODE_COLUMNS: Final = (
    "hash, client_id, session_id, account_id, family_id, redirect_uri, scope, nonce, code_challenge, auth_time, amr, "
    "expires_at, used_at"
)
_SESSION_COLUMNS: Final = "id_hash, account_id, auth_time, amr, created_at, expires_at, revoked_at"
_REFRESH_COLUMNS: Final = "hash, family_id, session_id, client_id, account_id, scope, status, created_at, rotated_to"


def _pending(row: Sequence[Any]) -> PendingAuthorization:
    names = _PENDING_COLUMNS.split(", ")
    return PendingAuthorization(**dict(zip(names, row, strict=True)))


def _pending_values(pending: PendingAuthorization) -> tuple[object, ...]:
    return tuple(getattr(pending, name) for name in _PENDING_COLUMNS.split(", "))


def _code(row: Sequence[Any]) -> AuthorizationCode:
    return AuthorizationCode(**dict(zip(_CODE_COLUMNS.split(", "), row, strict=True)))


def _session(row: Sequence[Any]) -> Session:
    return Session(**dict(zip(_SESSION_COLUMNS.split(", "), row, strict=True)))


def _refresh(row: Sequence[Any]) -> RefreshToken:
    return RefreshToken(**dict(zip(_REFRESH_COLUMNS.split(", "), row, strict=True)))


def _placeholders(columns: str) -> str:
    return ", ".join(["%s"] * len(columns.split(", ")))


class PostgresGrantStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def put_pending(self, pending: PendingAuthorization) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                f"INSERT INTO identity.pending_authorizations ({_PENDING_COLUMNS}) "
                f"VALUES ({_placeholders(_PENDING_COLUMNS)})",
                _pending_values(pending),
            )

    async def _pending_where(self, where: str, value: str) -> PendingAuthorization | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_PENDING_COLUMNS} FROM identity.pending_authorizations WHERE {where} = %s", (value,)
            )
            row = await cursor.fetchone()
        return _pending(row) if row is not None else None

    async def get_pending(self, id_hash: str) -> PendingAuthorization | None:
        return await self._pending_where("id_hash", id_hash)

    async def pending_by_google_state(self, state_hash: str) -> PendingAuthorization | None:
        return await self._pending_where("google_state_hash", state_hash)

    async def replace_pending(self, pending: PendingAuthorization) -> None:
        names = _PENDING_COLUMNS.split(", ")[1:]
        assignments = ", ".join(f"{name} = %s" for name in names)
        values = _pending_values(pending)
        async with self._pool.connection() as connection:
            await connection.execute(
                f"UPDATE identity.pending_authorizations SET {assignments} WHERE id_hash = %s",
                (*values[1:], values[0]),
            )

    async def take_pending(self, id_hash: str) -> PendingAuthorization | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"DELETE FROM identity.pending_authorizations WHERE id_hash = %s RETURNING {_PENDING_COLUMNS}",
                (id_hash,),
            )
            row = await cursor.fetchone()
        return _pending(row) if row is not None else None

    async def put_code(self, code: AuthorizationCode) -> None:
        values = tuple(getattr(code, name) for name in _CODE_COLUMNS.split(", "))
        async with self._pool.connection() as connection:
            await connection.execute(
                f"INSERT INTO identity.authorization_codes ({_CODE_COLUMNS}) VALUES ({_placeholders(_CODE_COLUMNS)})",
                values,
            )

    async def consume_code(self, hash: str, *, at: datetime) -> CodeUse | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "UPDATE identity.authorization_codes SET used_at = %s WHERE hash = %s AND used_at IS NULL "
                f"RETURNING {_CODE_COLUMNS}",
                (at, hash),
            )
            row = await cursor.fetchone()
            if row is not None:
                return CodeUse(code=_code(row), reused=False)
            cursor = await connection.execute(
                f"SELECT {_CODE_COLUMNS} FROM identity.authorization_codes WHERE hash = %s", (hash,)
            )
            row = await cursor.fetchone()
        return CodeUse(code=_code(row), reused=True) if row is not None else None

    async def create_session(self, session: Session) -> None:
        values = tuple(getattr(session, name) for name in _SESSION_COLUMNS.split(", "))
        async with self._pool.connection() as connection:
            await connection.execute(
                f"INSERT INTO identity.sessions ({_SESSION_COLUMNS}) VALUES ({_placeholders(_SESSION_COLUMNS)})",
                values,
            )

    async def get_session(self, id_hash: str) -> Session | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_SESSION_COLUMNS} FROM identity.sessions WHERE id_hash = %s", (id_hash,)
            )
            row = await cursor.fetchone()
        return _session(row) if row is not None else None

    async def _revoke_sessions(self, where: str, params: tuple[object, ...], *, at: datetime) -> None:
        async with self._pool.connection() as connection, connection.transaction():
            await connection.execute(
                "UPDATE identity.refresh_tokens SET status = 'revoked' WHERE status <> 'revoked' AND session_id IN "
                f"(SELECT id_hash FROM identity.sessions WHERE {where})",
                params,
            )
            await connection.execute(
                f"UPDATE identity.sessions SET revoked_at = %s WHERE revoked_at IS NULL AND {where}", (at, *params)
            )

    async def revoke_session(self, id_hash: str, *, at: datetime) -> None:
        await self._revoke_sessions("id_hash = %s", (id_hash,), at=at)

    async def revoke_account_sessions(self, account_id: str, *, at: datetime, keep: str | None = None) -> None:
        await self._revoke_sessions("account_id = %s AND id_hash IS DISTINCT FROM %s", (account_id, keep), at=at)

    async def revoke_all_sessions(self, *, at: datetime) -> None:
        await self._revoke_sessions("TRUE", (), at=at)

    async def put_refresh(self, token: RefreshToken) -> None:
        async with self._pool.connection() as connection:
            await self._insert_refresh(connection, token)

    @staticmethod
    async def _insert_refresh(connection: Any, token: RefreshToken) -> None:
        values = tuple(getattr(token, name) for name in _REFRESH_COLUMNS.split(", "))
        await connection.execute(
            f"INSERT INTO identity.refresh_tokens ({_REFRESH_COLUMNS}) VALUES ({_placeholders(_REFRESH_COLUMNS)})",
            values,
        )

    async def get_refresh(self, hash: str) -> RefreshToken | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {_REFRESH_COLUMNS} FROM identity.refresh_tokens WHERE hash = %s", (hash,)
            )
            row = await cursor.fetchone()
        return _refresh(row) if row is not None else None

    async def rotate_refresh(self, old_hash: str, new: RefreshToken) -> bool:
        async with self._pool.connection() as connection, connection.transaction():
            cursor = await connection.execute(
                "UPDATE identity.refresh_tokens SET status = 'rotated', rotated_to = %s "
                "WHERE hash = %s AND status = 'active'",
                (new.hash, old_hash),
            )
            if cursor.rowcount != 1:
                return False
            await self._insert_refresh(connection, new)
            return True

    async def revoke_family(self, family_id: str) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                "UPDATE identity.refresh_tokens SET status = 'revoked' WHERE family_id = %s", (family_id,)
            )

    async def purge(self, *, now: datetime, codes_before: datetime) -> int:
        removed = 0
        async with self._pool.connection() as connection, connection.transaction():
            for statement, params in (
                ("DELETE FROM identity.pending_authorizations WHERE expires_at <= %s", (now,)),
                ("DELETE FROM identity.authorization_codes WHERE expires_at <= %s", (codes_before,)),
                (
                    "DELETE FROM identity.refresh_tokens WHERE session_id IN (SELECT id_hash FROM identity.sessions "
                    "WHERE expires_at <= %s OR revoked_at IS NOT NULL)",
                    (now,),
                ),
                ("DELETE FROM identity.sessions WHERE expires_at <= %s OR revoked_at IS NOT NULL", (now,)),
            ):
                cursor = await connection.execute(statement, params)
                removed += max(cursor.rowcount, 0)
        return removed


# ---------------------------------------------------------------------------------------------------------------------
# Chaves e ajustes
# ---------------------------------------------------------------------------------------------------------------------


class PostgresSigningKeyStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def all(self) -> tuple[SigningKey, ...]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT kid, public_jwk, private_sealed, state, created_at, retiring_since FROM identity.signing_keys "
                "ORDER BY created_at, kid"
            )
            rows = await cursor.fetchall()
        return tuple(
            SigningKey(
                kid=kid,
                public_jwk=public_jwk,
                private_sealed=bytes(sealed),
                state=state,
                created_at=created_at,
                retiring_since=retiring_since,
            )
            for kid, public_jwk, sealed, state, created_at, retiring_since in rows
        )

    async def put(self, key: SigningKey) -> None:
        try:
            async with self._pool.connection() as connection:
                await connection.execute(
                    "INSERT INTO identity.signing_keys (kid, public_jwk, private_sealed, state, created_at, "
                    "retiring_since) VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        key.kid,
                        Jsonb(dict(key.public_jwk)),
                        key.private_sealed,
                        key.state,
                        key.created_at,
                        key.retiring_since,
                    ),
                )
        except UniqueViolation:
            raise Conflict(f"a chave {key.kid!r} já existe", field="kid") from None

    async def set_state(self, kid: str, state: KeyState, *, at: datetime) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                "UPDATE identity.signing_keys SET state = %s, "
                "retiring_since = CASE WHEN %s = 'retiring' THEN %s ELSE retiring_since END WHERE kid = %s",
                (state, state, at, kid),
            )


class PostgresIdentitySettingsStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self) -> IdentitySettings:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT google_enabled, version, updated_by, updated_at FROM identity.settings WHERE id = 1"
            )
            row = await cursor.fetchone()
        if row is None:
            return IdentitySettings()
        google_enabled, version, updated_by, updated_at = row
        return IdentitySettings(
            google_enabled=google_enabled, version=version, updated_by=updated_by, updated_at=updated_at
        )

    async def put(self, settings: IdentitySettings, *, expected_version: int) -> bool:
        values = (settings.google_enabled, settings.version, settings.updated_by, settings.updated_at)
        async with self._pool.connection() as connection:
            if expected_version == 0:
                cursor = await connection.execute(
                    "INSERT INTO identity.settings (id, google_enabled, version, updated_by, updated_at) "
                    "VALUES (1, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    values,
                )
            else:
                cursor = await connection.execute(
                    "UPDATE identity.settings SET google_enabled = %s, version = %s, updated_by = %s, updated_at = %s "
                    "WHERE id = 1 AND version = %s",
                    (*values, expected_version),
                )
        return cursor.rowcount == 1
