# Data model — 012 Identity

Value objects publicados em `api.py` (marcados **seam**) e registros internos das portas (`ports.py`). Tudo `frozen`,
`kw_only`, validado na construção.

## Vocabulário

| Nome | Regra |
|---|---|
| `USERNAME_PATTERN` | `^[a-z0-9][a-z0-9._-]{0,63}$` — sem `@`, imutável, nunca reaproveitado |
| `GROUP_PATTERN` | o mesmo padrão |
| e-mail | `strip().lower()`; único entre todas as contas, ativas ou não |
| senha | 12 a 128 caracteres (contados como código Unicode), sem regra de composição |
| `ClientType` | `"confidential" \| "public"` |
| `AuthMethod` (`amr`) | `"pwd" \| "google"` |

## Seam (`api.py`)

### `Account` (seam)

| Campo | Tipo | Nota |
|---|---|---|
| `id` | `str` | UUID; é o `sub` dos tokens |
| `username` | `str` | `USERNAME_PATTERN` |
| `email` | `str` | normalizado |
| `name` | `str` | 1–120 caracteres |
| `groups` | `frozenset[str]` | nomes de grupo existentes |
| `active` | `bool` | |
| `temporary_password` | `bool` | troca obrigatória no próximo login |
| `has_password` | `bool` | falso para conta só Google |
| `google_linked` | `bool` | |
| `created_at`, `updated_at` | `datetime` | UTC |
| `updated_by` | `str \| None` | subject do ator (`user:<nome>`, `cli`, `bootstrap`) |
| `last_login_at` | `datetime \| None` | |
| `version` | `int` | começa em 1; a 008 a usa como `version`/`If-Match` nas escritas |

### `AccountDraft` (seam) — cadastro

`username`, `email`, `name`, `groups`, `google_only: bool` (sem senha temporária).

### `AccountPatch` (seam) — alteração

`email`, `name`, `groups` — cada um opcional; `None` mantém.

### `IssuedPassword` (seam)

`account: Account`, `temporary_password: str` — devolvido só por `create` (sem `google_only`) e `reset_password`.

### `Group` (seam)

`name`, `members: int`, `protected: bool`.

### `LoginSettingsView` (seam)

| Campo | Tipo | Nota |
|---|---|---|
| `google_enabled` | `bool` | valor efetivo |
| `google_source` | `"installation" \| "runtime" \| "default"` | ADR-033 |
| `google_configured` | `bool` | cliente Google presente na instalação |
| `google_redirect_uri` | `str` | `{AXON_PUBLIC_URL}/oauth2/google/callback` |
| `google_client_id` | `str \| None` | público; nunca o segredo |
| `google_hosted_domain` | `str \| None` | |
| `version` | `int` | para `If-Match` na 008 |

### Erros (seam)

`IdentityError` (base) → `AccountNotFound`, `GroupNotFound`, `Conflict(field)` (nome ou e-mail em uso, versão
desatualizada), `InvalidField(field, reason)`, `ProtectedGroup(reason)` (apagar o grupo de admin; desativar ou tirar
dele o último admin ativo), `GoogleNotConfigured`, `InstallationDefined(field)`.

## Registros internos (`ports.py`)

### `AccountRecord`

`Account` (com a `version`) + `password_hash: str | None` + `google_sub: str | None`.

### `PendingAuthorization` — pedido de autorização aguardando login

`id` (opaco, 32 bytes, guardado como hash), `client_id` e `redirect_uri` (ausentes no login para "Minha conta"),
`scope`, `state`, `nonce`, `code_challenge` (só S256), `csrf_hash`, `account_id` (a senha conferiu e falta trocar a
temporária), `google_state_hash`/`google_nonce`/`google_verifier` (quando o fluxo segue para o Google), `created_at`,
`expires_at` (10 min).

### `AuthorizationCode`

`hash`, `client_id`, `session_id`, `account_id`, `family_id` (a renovação que sai dele), `redirect_uri`, `scope`,
`nonce`, `code_challenge`, `auth_time`, `amr`, `expires_at` (60 s), `used_at` (uso único; reuso revoga a família).

### `Session`

`id_hash`, `account_id`, `auth_time`, `amr`, `created_at`, `expires_at` (30 dias absoluto), `revoked_at`. O CSRF de
"Minha conta" é derivado do token da sessão (SHA-256 com prefixo próprio), sem estado: só quem tem o cookie o calcula.

### `RefreshToken`

`hash`, `family_id`, `session_id`, `client_id`, `account_id`, `scope`, `status` (`active` → `rotated` | `revoked`), `created_at`,
`rotated_to` (hash).

Transições:

```text
active --uso (público)--> rotated  [emite um novo active na mesma família]
active --uso (confidencial)--> active
rotated --reuso--> família inteira revoked
qualquer --logout | desativação | troca de senha (outras sessões) | rotação forçada--> revoked
```

### `SigningKey`

`kid`, `public_jwk: Mapping`, `private_sealed: bytes` (AES-GCM com a subchave HKDF), `state`
(`active` → `retiring` → `retired`), `created_at`, `retiring_since`.

### `IdentitySettings`

`google_enabled: bool | None` (None = padrão), `version: int`, `updated_by`, `updated_at`.

### `Client` (do arquivo `identity.yaml`)

`id`, `type`, `secret_ref: str | None` (confidencial), `audience`, `redirect_uris: tuple[str, ...]`,
`post_logout_redirect_uris: tuple[str, ...]`. Formato em [contracts/identity-yaml.md](contracts/identity-yaml.md).

## Tabelas (schema `identity`)

| Tabela | Chave | Colunas principais |
|---|---|---|
| `accounts` | `id` | `username` único, `email` único, `name`, `active`, `password_hash`, `temporary_password`, `google_sub` único quando não nulo, `created_at`, `updated_at`, `updated_by`, `last_login_at`, `version` |
| `groups` | `name` | `created_at` |
| `memberships` | (`account_id`, `group_name`) | FK com `ON DELETE CASCADE` no grupo |
| `pending_authorizations` | `id_hash` | colunas de `PendingAuthorization` |
| `authorization_codes` | `hash` | colunas de `AuthorizationCode` |
| `sessions` | `id_hash` | colunas de `Session` |
| `refresh_tokens` | `hash` | `family_id` indexado, `session_id` indexado |
| `signing_keys` | `kid` | `public_jwk jsonb`, `private_sealed bytea`, `state` |
| `settings` | `id = 1` | `google_enabled`, `version`, `updated_by`, `updated_at` |
| `schema_version` | `version` | padrão dos módulos (ADR-015) |
