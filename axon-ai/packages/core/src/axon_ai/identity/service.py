"""`IdentityService`: os três seams da 012 e os casos de uso de cada endpoint do protocolo (ADR-030).

Só fala com portas. As regras puras moram em `domain/`; o adapter HTTP (`adapters/http.py`) traduz cada desfecho de
`domain/outcomes.py` em página, redirecionamento ou JSON. Nenhum segredo sai em log, erro ou resposta (FR-020): os
eventos de segurança (FR-021, R15) levam usuário, cliente e motivo.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Final
from urllib.parse import urlencode, urlsplit

from axon_ai.identity.api import (
    ACTOR_PATTERN,
    Account,
    AccountDraft,
    AccountNotFound,
    AccountPatch,
    AuthMethod,
    Conflict,
    GoogleNotConfigured,
    Group,
    GroupNotFound,
    InstallationDefined,
    InvalidField,
    IssuedPassword,
    LoginSettingsView,
    Page,
    ProtectedGroup,
)
from axon_ai.identity.domain import keys as key_rules
from axon_ai.identity.domain.accounts import (
    PROTECTED_DELETE,
    PROTECTED_LAST_ADMIN,
    leaves_admin_group_empty,
    missing_groups,
)
from axon_ai.identity.domain.attempts import attempt_keys
from axon_ai.identity.domain.authorize import AuthorizationRequest, NoRedirect, RedirectError, read_authorization
from axon_ai.identity.domain.digest import digest, same, session_csrf
from axon_ai.identity.domain.google import GoogleAccept, decide_google
from axon_ai.identity.domain.names import is_username, password_problem, read_identifier
from axon_ai.identity.domain.outcomes import (
    EXPIRED,
    FORM_REJECTED,
    GOOGLE_UNAVAILABLE,
    AccountPage,
    ErrorPage,
    LoggedOut,
    LoginError,
    LoginForm,
    PasswordForm,
    Redirect,
    SignedIn,
    TokenResponse,
    token_error,
)
from axon_ai.identity.domain.pkce import s256, verifies
from axon_ai.identity.domain.refresh import decide_refresh, session_alive
from axon_ai.identity.domain.settings import google_login
from axon_ai.identity.domain.tokens import access_claims, access_subject, hinted_subject, id_claims, userinfo
from axon_ai.identity.ports import (
    AccountRecord,
    AccountStore,
    AuthorizationCode,
    Client,
    ClientSource,
    Clock,
    GoogleClient,
    GrantStore,
    IdentitySecrets,
    IdentitySettings,
    IdentitySettingsStore,
    LoginAttempts,
    PasswordHasher,
    PendingAuthorization,
    RefreshToken,
    SealError,
    SecretCipher,
    Session,
    SigningKey,
    SigningKeyStore,
    TokenGenerator,
    TokenSigner,
    UpstreamError,
    UpstreamOidc,
)

LOGGER: Final = "axon_ai.identity"
_log = logging.getLogger(LOGGER)

PAGE_LIMIT_MAX: Final = 200


class _Keep:
    """Marca "mantenha o valor atual" onde `None` é um valor legítimo (sem vínculo Google)."""


KEEP: Final = _Keep()


class IdentityStartError(RuntimeError):
    """A identidade não sobe: sem chave que abra com a chave mestra, por exemplo. A mensagem diz o que fazer."""


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityConfig:
    """O que a composition root decide para a 012 (contracts/configuration.md da 011)."""

    public_url: str
    admin_group: str
    access_ttl: timedelta = timedelta(minutes=10)
    session_ttl: timedelta = timedelta(days=30)
    code_ttl: timedelta = timedelta(seconds=60)
    pending_ttl: timedelta = timedelta(minutes=10)
    leeway: timedelta = timedelta(seconds=60)
    code_retention: timedelta = timedelta(hours=1)

    def __post_init__(self) -> None:
        parts = urlsplit(self.public_url)
        if parts.scheme not in ("http", "https") or not parts.netloc or parts.query or parts.fragment:
            raise ValueError("o endereço público precisa ser uma URL http(s) absoluta, sem query nem fragmento")
        object.__setattr__(self, "public_url", self.public_url.rstrip("/"))
        if not is_username(self.admin_group):
            raise ValueError(f"grupo de administração fora do padrão: {self.admin_group!r}")

    @property
    def issuer(self) -> str:
        return self.public_url


def _event(name: str, level: int = logging.INFO, **fields: object) -> None:
    """Evento de segurança (FR-021): nome e campos na mensagem e em `extra`. Nunca um segredo."""
    shown = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    _log.log(level, "%s %s", name, shown, extra={"identity": {"event": name, **fields}})


def _with_query(uri: str, params: Mapping[str, str | None]) -> str:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    return f"{uri}{'&' if '?' in uri else '?'}{query}"


class IdentityService:
    """Implementa `AccountAdmin`, `LoginSettings` e `PublicKeySet` (api.py) e o protocolo para `adapters/http.py`."""

    def __init__(
        self,
        *,
        config: IdentityConfig,
        accounts: AccountStore,
        grants: GrantStore,
        keys: SigningKeyStore,
        settings: IdentitySettingsStore,
        attempts: LoginAttempts,
        hasher: PasswordHasher,
        signer: TokenSigner,
        cipher: SecretCipher,
        clients: ClientSource,
        secrets: IdentitySecrets,
        clock: Clock,
        tokens: TokenGenerator,
        google: UpstreamOidc | None = None,
    ) -> None:
        self._config = config
        self._accounts = accounts
        self._grants = grants
        self._keys = keys
        self._settings = settings
        self._attempts = attempts
        self._hasher = hasher
        self._signer = signer
        self._cipher = cipher
        self._client_source = clients
        self._secrets = secrets
        self._clock = clock
        self._tokens = tokens
        self._google = google
        self._clients: dict[str, Client] = {}
        self._client_secrets: dict[str, str | None] = {}
        self._google_client: GoogleClient | None = None
        self._google_installation: bool | None = None
        self._jwks: Mapping[str, object] = MappingProxyType({"keys": []})
        self._signing: tuple[str, bytes] | None = None

    # -----------------------------------------------------------------------------------------------------------------
    # Ciclo de vida
    # -----------------------------------------------------------------------------------------------------------------

    async def start(self) -> None:
        """Lê clientes e segredos, garante o grupo de administração e uma chave `active` (FR-016) e carrega o JWKS."""
        self.load_configuration()
        await self.ensure_admin_group()
        await self._retire_due_keys()
        if key_rules.signing_key(await self._keys.all()) is None:
            await self._new_key()
        await self._reload_keys()

    async def ensure_admin_group(self) -> None:
        """O grupo de administração existe — também para a linha de comando criar o primeiro admin antes de o servidor
        subir pela primeira vez (FR-018)."""
        if self._config.admin_group not in await self._accounts.groups():
            await self._accounts.add_group(self._config.admin_group, at=self._clock.now())

    def load_configuration(self) -> None:
        """Clientes do `identity.yaml` e segredos da instalação. Cliente confidencial sem segredo fica indisponível."""
        clients = self._client_source.load()
        self._clients = {client.id: client for client in clients}
        self._client_secrets = {}
        for client in clients:
            if client.type != "confidential" or client.secret_ref is None:
                continue
            secret = self._secrets.client_secret(client.secret_ref)
            self._client_secrets[client.id] = secret
            if secret is None:
                _event(
                    "client.unavailable",
                    logging.WARNING,
                    client=client.id,
                    reason=f"defina AXON_IDENTITY_SECRET_{client.secret_ref.upper()}",
                )
        self._google_client = self._secrets.google()
        self._google_installation = self._secrets.google_login()

    @property
    def config(self) -> IdentityConfig:
        return self._config

    @property
    def clients(self) -> Mapping[str, Client]:
        return MappingProxyType(self._clients)

    def unavailable_clients(self) -> tuple[str, ...]:
        """Clientes confidenciais cuja variável de segredo falta (para a saúde da 011)."""
        return tuple(sorted(cid for cid, secret in self._client_secrets.items() if secret is None))

    async def purge(self) -> int:
        """Expurgo periódico (R12): pedidos, códigos, sessões e renovação vencidos; chaves em retirada vencidas."""
        now = self._clock.now()
        removed = await self._grants.purge(now=now, codes_before=now - self._config.code_retention)
        if await self._retire_due_keys():
            await self._reload_keys()
        return removed

    # -----------------------------------------------------------------------------------------------------------------
    # Chaves de assinatura — PublicKeySet
    # -----------------------------------------------------------------------------------------------------------------

    def jwks(self) -> Mapping[str, object]:
        return self._jwks

    async def rotate_keys(self, *, force: bool = False) -> str:
        """Nova chave `active`. Normal: a anterior fica publicada até vencer (SC-007). Forçada: tudo sai e as sessões
        caem — o caminho quando a chave mestra se perdeu ou a privada vazou."""
        now = self._clock.now()
        for kid, state in key_rules.to_retire_on_rotation(await self._keys.all(), force=force):
            await self._keys.set_state(kid, "retired" if state == "retired" else "retiring", at=now)
        kid = await self._new_key()
        if force:
            await self._grants.revoke_all_sessions(at=now)
        await self._reload_keys()
        _event("keys.rotated", kid=kid, force=force)
        return kid

    async def _new_key(self) -> str:
        generated = self._signer.generate_key()
        await self._keys.put(
            SigningKey(
                kid=generated.kid,
                public_jwk=generated.public_jwk,
                private_sealed=self._cipher.seal(generated.private_pem),
                state="active",
                created_at=self._clock.now(),
            )
        )
        return generated.kid

    async def _retire_due_keys(self) -> bool:
        grace = self._config.access_ttl + self._config.leeway
        now = self._clock.now()
        due = key_rules.due_for_retirement(await self._keys.all(), now=now, grace=grace)
        for kid in due:
            await self._keys.set_state(kid, "retired", at=now)
        return bool(due)

    async def _reload_keys(self) -> None:
        keys = await self._keys.all()
        active = key_rules.signing_key(keys)
        if active is None:
            raise IdentityStartError("nenhuma chave de assinatura ativa")
        try:
            pem = self._cipher.open(active.private_sealed)
        except SealError:
            raise IdentityStartError(
                "a chave de assinatura não abre com AXON_MASTER_KEY; restaure a chave mestra ou rode "
                "`axon identity keys rotate --force` (encerra todas as sessões)"
            ) from None
        self._signing = (active.kid, pem)
        self._jwks = MappingProxyType(key_rules.jwks(keys))

    def _sign(self, claims: Mapping[str, object]) -> str:
        if self._signing is None:
            raise IdentityStartError("a identidade não foi iniciada")
        kid, pem = self._signing
        return self._signer.sign(claims, kid=kid, private_pem=pem)

    # -----------------------------------------------------------------------------------------------------------------
    # Descoberta
    # -----------------------------------------------------------------------------------------------------------------

    def discovery(self, base_url: str) -> dict[str, object]:
        """Público pelo emissor; servidor a servidor pela base do pedido (FR-019, R8)."""
        public, base = self._config.public_url, base_url.rstrip("/")
        return {
            "issuer": self._config.issuer,
            "authorization_endpoint": f"{public}/oauth2/authorize",
            "end_session_endpoint": f"{public}/oauth2/logout",
            "token_endpoint": f"{base}/oauth2/token",
            "userinfo_endpoint": f"{base}/oauth2/userinfo",
            "jwks_uri": f"{base}/oauth2/jwks",
            "revocation_endpoint": f"{base}/oauth2/revoke",
            "response_types_supported": ["code"],
            "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
            "revocation_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": ["openid", "profile", "email", "groups", "offline_access"],
            "claims_supported": ["sub", "preferred_username", "name", "email", "email_verified", "groups"],
        }

    # -----------------------------------------------------------------------------------------------------------------
    # Autorização, login e troca obrigatória de senha
    # -----------------------------------------------------------------------------------------------------------------

    async def authorize(self, params: Mapping[str, str], session_token: str | None) -> Redirect | LoginForm | ErrorPage:
        request = read_authorization(params, self._clients)
        if isinstance(request, NoRedirect):
            return ErrorPage(status=400, title="Este link de login não é válido", message=request.reason)
        if isinstance(request, RedirectError):
            return Redirect(
                location=_with_query(
                    request.redirect_uri,
                    {"error": request.error, "error_description": request.description, "state": request.state},
                )
            )
        found = await self._live_session(session_token)
        if found is not None and request.prompt != "login":
            session, account = found
            return Redirect(location=await self._issue_code(request, session=session, account=account))
        if request.prompt == "none":
            return Redirect(
                location=_with_query(
                    request.redirect_uri,
                    {"error": "login_required", "error_description": "sem sessão", "state": request.state},
                )
            )
        return await self._new_pending(request)

    async def account_login(self) -> LoginForm:
        """Login sem cliente: a volta é a própria página "Minha conta"."""
        return await self._new_pending(None)

    async def _new_pending(self, request: AuthorizationRequest | None) -> LoginForm:
        now = self._clock.now()
        token, csrf = self._tokens.token(), self._tokens.token()
        await self._grants.put_pending(
            PendingAuthorization(
                id_hash=digest(token),
                csrf_hash=digest(csrf),
                client_id=request.client.id if request else None,
                redirect_uri=request.redirect_uri if request else None,
                scope=request.scope if request else "openid",
                state=request.state if request else None,
                nonce=request.nonce if request else None,
                code_challenge=request.code_challenge if request else None,
                created_at=now,
                expires_at=now + self._config.pending_ttl,
            )
        )
        return LoginForm(request=token, csrf=csrf, google=await self.google_available())

    async def _pending(self, token: str) -> PendingAuthorization | None:
        pending = await self._grants.get_pending(digest(token)) if token else None
        if pending is None or self._clock.now() >= pending.expires_at:
            return None
        return pending

    async def login(
        self, *, request: str, identifier: str, password: str, csrf: str, source: str | None
    ) -> LoginForm | PasswordForm | SignedIn | ErrorPage:
        pending = await self._pending(request)
        if pending is None:
            return EXPIRED
        if not same(digest(csrf), pending.csrf_hash):
            _event("login.failed", logging.WARNING, reason="csrf", client=pending.client_id)
            return FORM_REJECTED
        kind, value = read_identifier(identifier)
        keys = attempt_keys(identifier=value, source=source)
        now = self._clock.now()

        async def refuse(reason: str, username: str | None) -> LoginForm:
            self._attempts.fail(keys, now=now)
            _event("login.failed", user=username, client=pending.client_id, reason=reason, source=source)
            return await self._form_again(pending, request=request, csrf=csrf, identifier=identifier, error="invalid")

        if self._attempts.blocked(keys, now=now):
            await self._hasher.dummy_verify(password)
            _event("login.locked", logging.WARNING, identifier=value, client=pending.client_id, source=source)
            return await self._form_again(pending, request=request, csrf=csrf, identifier=identifier, error="invalid")
        record = await (self._accounts.by_email(value) if kind == "email" else self._accounts.by_username(value))
        if record is None or record.password_hash is None:
            await self._hasher.dummy_verify(password)
            if record is None:
                return await refuse("unknown", None)
            return await refuse("no_password", record.account.username)
        if not await self._hasher.verify(record.password_hash, password):
            return await refuse("password", record.account.username)
        if not record.account.active:
            return await refuse("disabled", record.account.username)
        self._attempts.reset(attempt_keys(identifier=value, source=None))
        if self._hasher.needs_rehash(record.password_hash):
            record = await self._save(record, password_hash=await self._hasher.hash(password), bump=False)
        if record.account.temporary_password:
            await self._grants.replace_pending(dataclasses.replace(pending, account_id=record.account.id))
            return PasswordForm(request=request, csrf=csrf)
        return await self._complete(pending, record, amr="pwd")

    async def change_temporary_password(
        self, *, request: str, csrf: str, new_password: str, confirm: str
    ) -> PasswordForm | SignedIn | ErrorPage:
        pending = await self._pending(request)
        if pending is None:
            return EXPIRED
        if not same(digest(csrf), pending.csrf_hash) or pending.account_id is None:
            return FORM_REJECTED
        record = await self._accounts.get(pending.account_id)
        if record is None or not record.account.active or not record.account.temporary_password:
            return EXPIRED
        errors = await self._new_password_errors(new_password, confirm)
        if not errors and record.password_hash and await self._hasher.verify(record.password_hash, new_password):
            errors["new_password"] = "A nova senha precisa ser diferente da temporária."
        if errors:
            return PasswordForm(request=request, csrf=csrf, errors=errors)
        record = await self._save(
            record,
            password_hash=await self._hasher.hash(new_password),
            temporary_password=False,
            actor=record.account.subject,
        )
        _event("account.password_changed", user=record.account.username, actor=record.account.subject)
        return await self._complete(pending, record, amr="pwd")

    async def _new_password_errors(self, new_password: str, confirm: str) -> dict[str, str]:
        errors: dict[str, str] = {}
        problem = password_problem(new_password)
        if problem is not None:
            errors["new_password"] = problem
        elif new_password != confirm:
            errors["confirm"] = "A confirmação não é igual à nova senha."
        return errors

    async def _form_again(
        self,
        pending: PendingAuthorization,
        *,
        request: str | None,
        csrf: str | None,
        identifier: str = "",
        error: LoginError | None = None,
        google_email: str | None = None,
    ) -> LoginForm:
        """De novo a página de login do mesmo pedido. Sem o id e o CSRF em claro (volta do Google), emite novos."""
        if request is None or csrf is None:
            await self._grants.take_pending(pending.id_hash)
            request, csrf = self._tokens.token(), self._tokens.token()
            pending = dataclasses.replace(
                pending,
                id_hash=digest(request),
                csrf_hash=digest(csrf),
                account_id=None,
                google_state_hash=None,
                google_nonce=None,
                google_verifier=None,
            )
            await self._grants.put_pending(pending)
        return LoginForm(
            request=request,
            csrf=csrf,
            google=await self.google_available(),
            identifier=identifier,
            error=error,
            google_email=google_email,
        )

    async def _complete(
        self, pending: PendingAuthorization, record: AccountRecord, *, amr: AuthMethod
    ) -> SignedIn | ErrorPage:
        """Login concluído: tira o pedido (uma vez só), abre a sessão e volta ao cliente com o código."""
        if await self._grants.take_pending(pending.id_hash) is None:
            return EXPIRED
        now = self._clock.now()
        session_token = self._tokens.token()
        session = Session(
            id_hash=digest(session_token),
            account_id=record.account.id,
            auth_time=now,
            amr=amr,
            created_at=now,
            expires_at=now + self._config.session_ttl,
        )
        await self._grants.create_session(session)
        record = await self._save(record, last_login_at=now, bump=False)
        _event("login.ok", user=record.account.username, client=pending.client_id, method=amr)
        if pending.client_id is None:
            location = f"{self._config.public_url}/oauth2/account"
        else:
            client = self._clients.get(pending.client_id)
            if client is None or pending.redirect_uri is None:
                return EXPIRED
            request = AuthorizationRequest(
                client=client,
                redirect_uri=pending.redirect_uri,
                scope=pending.scope,
                nonce=pending.nonce or "",
                state=pending.state,
                code_challenge=pending.code_challenge,
            )
            location = await self._issue_code(request, session=session, account=record.account)
        return SignedIn(
            session_token=session_token, max_age=int(self._config.session_ttl.total_seconds()), location=location
        )

    async def _issue_code(self, request: AuthorizationRequest, *, session: Session, account: Account) -> str:
        now = self._clock.now()
        code = self._tokens.token()
        await self._grants.put_code(
            AuthorizationCode(
                hash=digest(code),
                client_id=request.client.id,
                session_id=session.id_hash,
                account_id=account.id,
                family_id=self._tokens.uuid(),
                redirect_uri=request.redirect_uri,
                scope=request.scope,
                nonce=request.nonce or None,
                code_challenge=request.code_challenge,
                auth_time=session.auth_time,
                amr=session.amr,
                expires_at=now + self._config.code_ttl,
            )
        )
        return _with_query(request.redirect_uri, {"code": code, "state": request.state})

    async def _live_session(self, session_token: str | None) -> tuple[Session, Account] | None:
        """Sessão válida de conta ativa, sem senha temporária pendente (FR-015)."""
        if not session_token:
            return None
        session = await self._grants.get_session(digest(session_token))
        if session is None or not session_alive(session, now=self._clock.now()):
            return None
        record = await self._accounts.get(session.account_id)
        if record is None or not record.account.active or record.account.temporary_password:
            return None
        return session, record.account

    # -----------------------------------------------------------------------------------------------------------------
    # Token, userinfo, revogação e logout
    # -----------------------------------------------------------------------------------------------------------------

    def _authenticate_client(self, form: Mapping[str, str], basic: tuple[str, str] | None) -> Client | TokenResponse:
        posted_secret = form.get("client_secret")
        if basic is not None and posted_secret is not None:
            return token_error("invalid_request", "use um só método de autenticação do cliente")
        client_id, secret = basic if basic is not None else (form.get("client_id", ""), posted_secret)
        client = self._clients.get(client_id)
        if client is None:
            return token_error("invalid_client", "cliente desconhecido", status=401)
        if client.type == "public":
            if secret is not None:
                return token_error("invalid_client", "cliente público não tem segredo", status=401)
            return client
        expected = self._client_secrets.get(client.id)
        if expected is None or secret is None or not same(secret, expected):
            return token_error("invalid_client", "autenticação do cliente falhou", status=401)
        return client

    async def token(self, form: Mapping[str, str], basic: tuple[str, str] | None) -> TokenResponse:
        client = self._authenticate_client(form, basic)
        if isinstance(client, TokenResponse):
            return client
        grant = form.get("grant_type")
        if grant == "authorization_code":
            return await self._exchange_code(client, form)
        if grant == "refresh_token":
            return await self._refresh(client, form)
        return token_error("unsupported_grant_type", "só authorization_code e refresh_token")

    async def _exchange_code(self, client: Client, form: Mapping[str, str]) -> TokenResponse:
        now = self._clock.now()
        use = await self._grants.consume_code(digest(form.get("code", "")), at=now) if form.get("code") else None
        if use is None:
            return token_error("invalid_grant", "código inválido")
        code = use.code
        if use.reused:
            await self._grants.revoke_family(code.family_id)
            _event("token.code_reused", logging.WARNING, client=client.id, account=code.account_id)
            return token_error("invalid_grant", "código já usado")
        if code.client_id != client.id or now >= code.expires_at or form.get("redirect_uri") != code.redirect_uri:
            return token_error("invalid_grant", "código inválido")
        if code.code_challenge is not None and not verifies(form.get("code_verifier"), code.code_challenge):
            return token_error("invalid_grant", "code_verifier não confere")
        session = await self._grants.get_session(code.session_id)
        record = await self._accounts.get(code.account_id)
        if not session_alive(session, now=now) or record is None or not record.account.active:
            return token_error("invalid_grant", "sessão encerrada")
        refresh = self._tokens.token()
        await self._grants.put_refresh(
            RefreshToken(
                hash=digest(refresh),
                family_id=code.family_id,
                session_id=code.session_id,
                client_id=client.id,
                account_id=code.account_id,
                scope=code.scope,
                created_at=now,
            )
        )
        return self._tokens_response(
            client,
            record.account,
            scope=code.scope,
            nonce=code.nonce,
            auth_time=code.auth_time,
            amr=code.amr,
            refresh=refresh,
        )

    async def _refresh(self, client: Client, form: Mapping[str, str]) -> TokenResponse:
        now = self._clock.now()
        presented = form.get("refresh_token", "")
        token = await self._grants.get_refresh(digest(presented)) if presented else None
        session = await self._grants.get_session(token.session_id) if token else None
        record = await self._accounts.get(token.account_id) if token else None
        decision = decide_refresh(
            token, client=client, session=session, account=record.account if record else None, now=now
        )
        if decision == "invalid" or token is None or session is None or record is None:
            return token_error("invalid_grant", "token de renovação inválido")
        if decision == "reuse":
            return await self._refresh_reused(client, token)
        refresh = presented
        if decision == "rotate":
            refresh = self._tokens.token()
            rotated = RefreshToken(
                hash=digest(refresh),
                family_id=token.family_id,
                session_id=token.session_id,
                client_id=client.id,
                account_id=token.account_id,
                scope=token.scope,
                created_at=now,
            )
            if not await self._grants.rotate_refresh(token.hash, rotated):
                return await self._refresh_reused(client, token)
        return self._tokens_response(
            client,
            record.account,
            scope=token.scope,
            nonce=None,
            auth_time=session.auth_time,
            amr=session.amr,
            refresh=refresh,
        )

    async def _refresh_reused(self, client: Client, token: RefreshToken) -> TokenResponse:
        await self._grants.revoke_family(token.family_id)
        _event("token.refresh_reused", logging.WARNING, client=client.id, account=token.account_id)
        return token_error("invalid_grant", "token de renovação já usado")

    def _tokens_response(
        self,
        client: Client,
        account: Account,
        *,
        scope: str,
        nonce: str | None,
        auth_time: datetime,
        amr: AuthMethod,
        refresh: str,
    ) -> TokenResponse:
        now, ttl, issuer = self._clock.now(), self._config.access_ttl, self._config.issuer
        access = self._sign(access_claims(issuer=issuer, client=client, account=account, scope=scope, now=now, ttl=ttl))
        identity = self._sign(
            id_claims(
                issuer=issuer,
                client=client,
                account=account,
                nonce=nonce,
                auth_time=auth_time,
                amr=amr,
                now=now,
                ttl=ttl,
            )
        )
        return TokenResponse(
            status=200,
            body={
                "access_token": access,
                "token_type": "Bearer",
                "expires_in": int(ttl.total_seconds()),
                "id_token": identity,
                "refresh_token": refresh,
                "scope": scope,
            },
        )

    async def userinfo(self, bearer: str | None) -> dict[str, object] | None:
        if not bearer:
            return None
        claims = self._signer.verify(bearer, self._jwks)
        if claims is None:
            return None
        subject = access_subject(
            claims,
            issuer=self._config.issuer,
            audiences={client.audience for client in self._clients.values()},
            now=self._clock.now(),
            leeway=self._config.leeway,
        )
        record = await self._accounts.get(subject) if subject else None
        if record is None or not record.account.active:
            return None
        return userinfo(record.account)

    async def revoke(self, form: Mapping[str, str], basic: tuple[str, str] | None) -> TokenResponse:
        """RFC 7009: revoga a família da renovação do cliente autenticado; responde 200 mesmo sem achar nada."""
        client = self._authenticate_client(form, basic)
        if isinstance(client, TokenResponse):
            return client
        presented = form.get("token", "")
        token = await self._grants.get_refresh(digest(presented)) if presented else None
        if token is not None and token.client_id == client.id:
            await self._grants.revoke_family(token.family_id)
        return TokenResponse(status=200, body={})

    async def logout(self, params: Mapping[str, str], session_token: str | None) -> LoggedOut:
        client: Client | None = None
        hint = params.get("id_token_hint")
        if hint:
            claims = self._signer.verify(hint, self._jwks)
            found = hinted_subject(claims, issuer=self._config.issuer, client_ids=self._clients) if claims else None
            if found is not None:
                client = self._clients[found[1]]
        if client is None and params.get("client_id") in self._clients:
            client = self._clients[params["client_id"]]
        if session_token:
            session = await self._grants.get_session(digest(session_token))
            if session is not None:
                await self._grants.revoke_session(session.id_hash, at=self._clock.now())
                _event("logout", account=session.account_id, client=client.id if client else None)
        target = params.get("post_logout_redirect_uri")
        if client is not None and target and target in client.post_logout_redirect_uris:
            return LoggedOut(location=_with_query(target, {"state": params.get("state") or None}))
        return LoggedOut()

    # -----------------------------------------------------------------------------------------------------------------
    # "Minha conta"
    # -----------------------------------------------------------------------------------------------------------------

    async def account_page(self, session_token: str | None) -> AccountPage | LoginForm:
        found = await self._live_session(session_token)
        if found is None or session_token is None:
            return await self.account_login()
        _, account = found
        return AccountPage(account=account, csrf=session_csrf(session_token) if account.has_password else None)

    async def change_own_password(
        self,
        *,
        session_token: str | None,
        csrf: str,
        current_password: str,
        new_password: str,
        confirm: str,
        source: str | None,
    ) -> AccountPage | LoginForm | ErrorPage:
        found = await self._live_session(session_token)
        if found is None or session_token is None:
            return await self.account_login()
        if not same(csrf, session_csrf(session_token)):
            return FORM_REJECTED
        session, account = found
        record = await self._accounts.get(account.id)
        if record is None or record.password_hash is None:
            return AccountPage(account=account, csrf=None)
        page_csrf = session_csrf(session_token)
        keys = attempt_keys(identifier=account.username, source=source)
        now = self._clock.now()
        if self._attempts.blocked(keys, now=now):
            await self._hasher.dummy_verify(current_password)
            _event("login.locked", logging.WARNING, user=account.username, source=source)
            message = "Muitas tentativas. Espere 15 minutos e tente de novo."
            return AccountPage(account=account, csrf=page_csrf, errors={"current_password": message})
        if not await self._hasher.verify(record.password_hash, current_password):
            self._attempts.fail(keys, now=now)
            _event("login.failed", user=account.username, reason="account_password", source=source)
            return AccountPage(
                account=account, csrf=page_csrf, errors={"current_password": "A senha atual não confere."}
            )
        errors = await self._new_password_errors(new_password, confirm)
        if errors:
            return AccountPage(account=account, csrf=page_csrf, errors=errors)
        record = await self._save(
            record, password_hash=await self._hasher.hash(new_password), temporary_password=False, actor=account.subject
        )
        await self._grants.revoke_account_sessions(account.id, at=now, keep=session.id_hash)
        _event("account.password_changed", user=account.username, actor=account.subject)
        return AccountPage(
            account=record.account,
            csrf=page_csrf,
            message="Senha trocada. As suas outras sessões foram encerradas.",
        )

    # -----------------------------------------------------------------------------------------------------------------
    # Google
    # -----------------------------------------------------------------------------------------------------------------

    async def google_available(self) -> bool:
        if self._google is None or self._google_client is None:
            return False
        stored = await self._settings.get()
        enabled, _ = google_login(
            installation=self._google_installation, runtime=stored.google_enabled, configured=True
        )
        return enabled

    async def google_start(self, request: str) -> Redirect | ErrorPage:
        if self._google is None or not await self.google_available():
            return GOOGLE_UNAVAILABLE
        pending = await self._pending(request)
        if pending is None:
            return EXPIRED
        state, nonce, verifier = self._tokens.token(), self._tokens.token(), self._tokens.token(48)
        await self._grants.replace_pending(
            dataclasses.replace(
                pending,
                account_id=None,
                google_state_hash=digest(state),
                google_nonce=nonce,
                google_verifier=verifier,
            )
        )
        url = await self._google.authorization_url(state=state, nonce=nonce, code_challenge=s256(verifier))
        return Redirect(location=url)

    async def google_callback(self, params: Mapping[str, str]) -> SignedIn | LoginForm | ErrorPage:
        state = params.get("state", "")
        pending = await self._grants.pending_by_google_state(digest(state)) if state else None
        if pending is None or self._clock.now() >= pending.expires_at:
            return EXPIRED
        if self._google is None or not await self.google_available():
            return GOOGLE_UNAVAILABLE
        code, verifier = params.get("code"), pending.google_verifier
        if params.get("error") or not code or verifier is None:
            _event("google.refused", client=pending.client_id, reason=params.get("error") or "no_code")
            return await self._form_again(pending, request=None, csrf=None, error="google_refused")
        try:
            identity = await self._google.exchange(code=code, code_verifier=verifier)
        except UpstreamError as error:
            _event("google.refused", logging.WARNING, client=pending.client_id, reason=f"upstream: {error}")
            return await self._form_again(pending, request=None, csrf=None, error="google_refused")
        email = identity.email.strip().lower() if identity.email else None
        decision = decide_google(
            identity,
            expected_nonce=pending.google_nonce,
            hosted_domain=self._google_client.hosted_domain if self._google_client else None,
            by_sub=await self._accounts.by_google_sub(identity.sub),
            by_email=await self._accounts.by_email(email) if email else None,
        )
        if not isinstance(decision, GoogleAccept):
            _event("google.refused", client=pending.client_id, reason=decision.reason)
            if decision.reason == "unknown":
                return await self._form_again(
                    pending, request=None, csrf=None, error="google_unknown", google_email=decision.email
                )
            return await self._form_again(pending, request=None, csrf=None, error="google_refused")
        record = await self._accounts.get(decision.account_id)
        if record is None:
            return EXPIRED
        if decision.link:
            record = await self._save(record, google_sub=identity.sub, actor=record.account.subject)
            _event("account.google_linked", user=record.account.username)
        return await self._complete(pending, record, amr="google")

    # -----------------------------------------------------------------------------------------------------------------
    # LoginSettings
    # -----------------------------------------------------------------------------------------------------------------

    async def view(self) -> LoginSettingsView:
        stored = await self._settings.get()
        configured = self._google_client is not None
        enabled, source = google_login(
            installation=self._google_installation, runtime=stored.google_enabled, configured=configured
        )
        return LoginSettingsView(
            google_enabled=enabled,
            google_source=source,
            google_configured=configured,
            google_redirect_uri=f"{self._config.public_url}/oauth2/google/callback",
            google_client_id=self._google_client.client_id if self._google_client else None,
            google_hosted_domain=self._google_client.hosted_domain if self._google_client else None,
            version=stored.version,
        )

    async def set_google(self, enabled: bool, *, actor: str, version: int) -> LoginSettingsView:
        _check_actor(actor)
        if self._google_installation is not None:
            raise InstallationDefined(
                "o login Google é definido pela instalação (AXON_GOOGLE_LOGIN)", field="google_enabled"
            )
        if enabled and self._google_client is None:
            raise GoogleNotConfigured(
                "configure AXON_GOOGLE_CLIENT_ID e AXON_GOOGLE_CLIENT_SECRET na instalação antes de ligar"
            )
        stored = await self._settings.get()
        updated = IdentitySettings(
            google_enabled=enabled, version=version + 1, updated_by=actor, updated_at=self._clock.now()
        )
        if stored.version != version or not await self._settings.put(updated, expected_version=version):
            current = await self._settings.get()
            raise Conflict("os ajustes mudaram desde a leitura", field="version", current_version=current.version)
        _event("settings.google", actor=actor, enabled=enabled)
        return await self.view()

    # -----------------------------------------------------------------------------------------------------------------
    # AccountAdmin
    # -----------------------------------------------------------------------------------------------------------------

    async def accounts(
        self, *, query: str | None = None, active: bool | None = True, limit: int = 50, cursor: str | None = None
    ) -> Page[Account]:
        size = max(1, min(limit, PAGE_LIMIT_MAX))
        found = await self._accounts.list(query=query, active=active, limit=size + 1, after=cursor)
        items = tuple(record.account for record in found[:size])
        return Page(items=items, next_cursor=items[-1].username if len(found) > size else None)

    async def account(self, username: str) -> Account:
        return (await self._record(username)).account

    async def _record(self, username: str) -> AccountRecord:
        record = await self._accounts.by_username(username)
        if record is None:
            raise AccountNotFound(f"a conta {username!r} não existe")
        return record

    async def create(self, draft: AccountDraft, *, actor: str) -> IssuedPassword | Account:
        _check_actor(actor)
        await self._check_groups(draft.groups)
        temporary = None if draft.google_only else self._tokens.password()
        record = await self._insert(
            username=draft.username,
            email=draft.email,
            name=draft.name,
            groups=draft.groups,
            password_hash=await self._hasher.hash(temporary) if temporary else None,
            temporary=temporary is not None,
            actor=actor,
        )
        if temporary is None:
            return record.account
        return IssuedPassword(account=record.account, temporary_password=temporary)

    async def create_with_password(self, draft: AccountDraft, password: str, *, actor: str) -> Account:
        """Cadastro pela linha de comando (R14): a senha é a definitiva da pessoa, não temporária."""
        _check_actor(actor)
        problem = password_problem(password)
        if problem is not None:
            raise InvalidField(problem, field="password")
        await self._check_groups(draft.groups)
        record = await self._insert(
            username=draft.username,
            email=draft.email,
            name=draft.name,
            groups=draft.groups,
            password_hash=await self._hasher.hash(password),
            temporary=False,
            actor=actor,
        )
        return record.account

    async def _insert(
        self,
        *,
        username: str,
        email: str,
        name: str,
        groups: frozenset[str],
        password_hash: str | None,
        temporary: bool,
        actor: str,
    ) -> AccountRecord:
        now = self._clock.now()
        account = Account(
            id=self._tokens.uuid(),
            username=username,
            email=email,
            name=name,
            groups=groups,
            temporary_password=temporary,
            has_password=password_hash is not None,
            created_at=now,
            updated_at=now,
            updated_by=actor,
        )
        record = AccountRecord(account=account, password_hash=password_hash)
        await self._accounts.insert(record)
        _event("account.created", user=username, actor=actor, groups=",".join(sorted(groups)) or None)
        return record

    async def update(self, username: str, patch: AccountPatch, *, actor: str, version: int) -> Account:
        _check_actor(actor)
        record = await self._record(username)
        if record.account.version != version:
            raise Conflict("a conta mudou desde a leitura", field="version", current_version=record.account.version)
        groups = record.account.groups if patch.groups is None else patch.groups
        if patch.groups is not None:
            await self._check_groups(groups)
            await self._guard_admin(record, active=record.account.active, groups=groups)
        updated = await self._save(
            record,
            email=patch.email if patch.email is not None else record.account.email,
            name=patch.name if patch.name is not None else record.account.name,
            groups=groups,
            actor=actor,
            expected=version,
        )
        _event("account.updated", user=username, actor=actor)
        return updated.account

    async def reset_password(self, username: str, *, actor: str) -> IssuedPassword:
        _check_actor(actor)
        record = await self._record(username)
        temporary = self._tokens.password()
        updated = await self._save(
            record, password_hash=await self._hasher.hash(temporary), temporary_password=True, actor=actor
        )
        await self._grants.revoke_account_sessions(record.account.id, at=self._clock.now())
        _event("account.password_reset", user=username, actor=actor)
        return IssuedPassword(account=updated.account, temporary_password=temporary)

    async def disable(self, username: str, *, actor: str) -> Account:
        _check_actor(actor)
        record = await self._record(username)
        if not record.account.active:
            return record.account
        await self._guard_admin(record, active=False, groups=record.account.groups)
        updated = await self._save(record, active=False, actor=actor)
        await self._grants.revoke_account_sessions(record.account.id, at=self._clock.now())
        _event("account.disabled", user=username, actor=actor)
        return updated.account

    async def enable(self, username: str, *, actor: str) -> Account:
        _check_actor(actor)
        record = await self._record(username)
        if record.account.active:
            return record.account
        updated = await self._save(record, active=True, actor=actor)
        _event("account.enabled", user=username, actor=actor)
        return updated.account

    async def unlink_google(self, username: str, *, actor: str) -> Account:
        _check_actor(actor)
        record = await self._record(username)
        if record.google_sub is None:
            return record.account
        updated = await self._save(record, google_sub=None, actor=actor)
        _event("account.google_unlinked", user=username, actor=actor)
        return updated.account

    async def groups(self) -> tuple[Group, ...]:
        counts = await self._accounts.groups()
        return tuple(
            Group(name=name, members=count, protected=name == self._config.admin_group)
            for name, count in counts.items()
        )

    async def create_group(self, name: str, *, actor: str) -> Group:
        _check_actor(actor)
        if not is_username(name):
            raise InvalidField("o nome do grupo precisa casar com [a-z0-9][a-z0-9._-]{0,63}", field="name")
        await self._accounts.add_group(name, at=self._clock.now())
        _event("group.created", group=name, actor=actor)
        return Group(name=name, protected=name == self._config.admin_group)

    async def delete_group(self, name: str, *, actor: str) -> None:
        _check_actor(actor)
        if name == self._config.admin_group:
            raise ProtectedGroup(PROTECTED_DELETE)
        if not await self._accounts.remove_group(name, at=self._clock.now(), actor=actor):
            raise GroupNotFound(f"o grupo {name!r} não existe")
        _event("group.deleted", group=name, actor=actor)

    async def set_members(self, name: str, usernames: frozenset[str], *, actor: str) -> Group:
        _check_actor(actor)
        counts = await self._accounts.groups()
        if name not in counts:
            raise GroupNotFound(f"o grupo {name!r} não existe")
        records: list[AccountRecord] = []
        for username in sorted(usernames):
            record = await self._accounts.by_username(username)
            if record is None:
                raise InvalidField(f"a conta {username!r} não existe", field="members")
            records.append(record)
        if name == self._config.admin_group:
            before = await self._accounts.active_members(name)
            after = {record.account.id for record in records if record.account.active}
            if leaves_admin_group_empty(before=before, after=after):
                raise ProtectedGroup(PROTECTED_LAST_ADMIN)
        await self._accounts.set_members(
            name, [record.account.id for record in records], at=self._clock.now(), actor=actor
        )
        _event("group.members", group=name, actor=actor, members=len(records))
        counts = await self._accounts.groups()
        return Group(name=name, members=counts.get(name, 0), protected=name == self._config.admin_group)

    async def bootstrap_admin(self) -> Account | None:
        """Admin inicial das variáveis da instalação, só com zero contas (FR-018)."""
        admin = self._secrets.bootstrap_admin()
        if admin is None:
            return None
        if await self._accounts.count() > 0:
            _event(
                "bootstrap.ignored", logging.WARNING, reason="já existem contas; variáveis do admin inicial ignoradas"
            )
            return None
        await self.ensure_admin_group()
        draft = AccountDraft(
            username=admin.username,
            email=admin.email,
            name=admin.username,
            groups=frozenset({self._config.admin_group}),
        )
        return await self.create_with_password(draft, admin.password, actor="bootstrap")

    async def _check_groups(self, groups: frozenset[str]) -> None:
        missing = missing_groups(groups, await self._accounts.groups())
        if missing:
            raise InvalidField(f"o grupo {missing[0]!r} não existe", field="groups")

    async def _guard_admin(self, record: AccountRecord, *, active: bool, groups: frozenset[str]) -> None:
        """Último membro ativo do grupo de administração não sai nem é desativado (FR-011)."""
        admin = self._config.admin_group
        if admin not in record.account.groups or not record.account.active:
            return
        if active and admin in groups:
            return
        before = await self._accounts.active_members(admin)
        if leaves_admin_group_empty(before=before, after=before - {record.account.id}):
            raise ProtectedGroup(PROTECTED_LAST_ADMIN)

    async def _save(
        self,
        record: AccountRecord,
        *,
        actor: str | None = None,
        bump: bool = True,
        expected: int | None = None,
        email: str | None = None,
        name: str | None = None,
        groups: frozenset[str] | None = None,
        active: bool | None = None,
        temporary_password: bool | None = None,
        last_login_at: datetime | None = None,
        password_hash: str | _Keep = KEEP,
        google_sub: str | _Keep | None = KEEP,
    ) -> AccountRecord:
        """Grava a conta com versão otimista. `bump=False` (último login, re-hash) não muda versão nem autor."""
        current = record.account
        new_hash = record.password_hash if isinstance(password_hash, _Keep) else password_hash
        new_sub = record.google_sub if isinstance(google_sub, _Keep) else google_sub
        account = dataclasses.replace(
            current,
            email=current.email if email is None else email,
            name=current.name if name is None else name,
            groups=current.groups if groups is None else groups,
            active=current.active if active is None else active,
            temporary_password=current.temporary_password if temporary_password is None else temporary_password,
            last_login_at=current.last_login_at if last_login_at is None else last_login_at,
            has_password=new_hash is not None,
            google_linked=new_sub is not None,
        )
        if bump:
            account = dataclasses.replace(
                account, updated_at=self._clock.now(), updated_by=actor, version=current.version + 1
            )
        updated = AccountRecord(account=account, password_hash=new_hash, google_sub=new_sub)
        await self._accounts.replace(updated, expected_version=current.version if expected is None else expected)
        return updated


def _check_actor(actor: str) -> None:
    if not ACTOR_PATTERN.fullmatch(actor):
        raise ValueError(f"ator inválido: {actor!r}")
