# Contrato — portas secundárias da 012 (`ports.py`)

Toda porta tem adapter em memória (`adapters/memory.py`) e suíte de conformidade em `tests/identity/contract/` que roda
contra ele e contra o real.

| Porta | Métodos principais | Real | Memória / teste | Conformidade |
|---|---|---|---|---|
| `AccountStore` | `get(id)`, `by_username`, `by_email`, `by_google_sub`, `list(query, active, limit, cursor)`, `insert`, `replace(record, expected_version)`, `groups()`, `add_group`, `remove_group`, `set_members`, `admins_active(group)` | Postgres `identity.accounts`/`groups`/`memberships` | dicionários | unicidade de nome e e-mail (case), versão, cascata de grupo |
| `GrantStore` | pedidos pendentes (`put`, `take`), códigos (`put`, `consume` atômico), sessões (`create`, `get`, `revoke`, `revoke_for_account`, `revoke_except`), renovação (`put`, `rotate` atômico, `revoke_family`, `revoke_for_session`), `purge(now)` | Postgres `identity.*` | dicionários | uso único do código sob concorrência, reuso de renovação revoga família, expurgo |
| `SigningKeyStore` | `all()`, `put`, `set_state` | Postgres `identity.signing_keys` | lista | estados e ordem |
| `IdentitySettingsStore` | `get()`, `put(settings, expected_version)` | Postgres `identity.settings` | valor | versão |
| `LoginAttempts` | `blocked(keys, now)`, `fail(keys, now)`, `reset(keys)` | memória (processo único) | o mesmo | janelas com relógio fixo |
| `PasswordHasher` | `hash`, `verify`, `needs_rehash`, `dummy_verify` | argon2id | hash rápido determinístico | verificação, re-hash, tempo do fictício |
| `TokenSigner` | `sign(claims, key)`, `generate_key() -> (kid, public_jwk, private_pem)`, `verify(token, jwks)` | `pyjwt[crypto]` + `cryptography` | o real com chave pequena de teste | ida e volta; `kid`; recusa de alg |
| `SecretCipher` | `seal(bytes) -> bytes`, `open(bytes) -> bytes` | AES-GCM + HKDF (`ai-core/identity/v1`) | o real com chave fixa | ida e volta; chave errada falha |
| `UpstreamOidc` | `authorization_url(state, nonce, verifier)`, `exchange(code, verifier) -> GoogleIdentity` | Google (`httpx` + `pyjwt`) | provedor simulado programável | `email_verified`, `hd`, `nonce` |
| `ClientSource` | `load() -> tuple[Client, ...]` | `identity.yaml` | lista | erros nomeando o campo |
| `IdentitySecrets` | `client_secret(ref)`, `google()`, `bootstrap_admin()` | ambiente (`AXON_IDENTITY_SECRET_<REF>`, `AXON_GOOGLE_*`, `AXON_BOOTSTRAP_ADMIN_*`) | dicionário | nomes fixos; nada de nome arbitrário (ADR-020) |
| `Clock` | `now()` | relógio do sistema (o da 011) | relógio fixo | — |
| `TokenGenerator` | `token(nbytes)`, `uuid()`, `password()` | `secrets` | sequência determinística | formato |

Import-linter: `identity.api`, `domain`, `ports` e `service` não importam `jwt`, `cryptography`, `argon2`, `httpx`,
`psycopg`, `psycopg_pool`, `yaml`, `fastapi`, `starlette`; outros módulos importam só `identity.api`; o adapter HTTP
importa `fastapi` como o da 008.
