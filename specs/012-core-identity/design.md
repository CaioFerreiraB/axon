# Design — 012 Identity

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: ADR-030 (a plataforma é o provedor de identidade), ADR-031
> (superfície de administração e audiência da console), ADR-033 (segredos de runtime cifrados), ADR-012, ADR-015,
> ADR-020; plano da Fase 9 (2026-10-13).

## Localização

```text
ai-core/packages/core/src/ai_core/identity/
├── api.py        # seams: AccountAdmin, LoginSettings, PublicKeySet; value objects Account, Group,
│                 # AccountDraft, LoginSettingsView (valor + origem), PublicKey; erros
├── domain/       # puro: validação do pedido de autorização, PKCE, regras de código e de renovação,
│                 # montagem de claims, decisão de bloqueio, decisão de vínculo Google, nomes e senhas
├── ports.py      # AccountStore, GrantStore, SigningKeyStore, IdentitySettingsStore, LoginAttempts,
│                 # PasswordHasher, TokenSigner, SecretCipher, UpstreamOidc, ClientSource, IdentitySecrets,
│                 # Clock, TokenGenerator
├── service.py    # IdentityService (implementa os seams e o caso de uso de cada endpoint)
└── adapters/
    ├── http.py              # adapter primário: router com os endpoints do protocolo e a página de login
    ├── templates/, static/  # página de login, troca de senha, erro (HTML + CSS, sem script inline)
    ├── memory.py            # adapters em memória de todas as portas de armazenamento
    ├── postgres.py          # AccountStore, GrantStore, SigningKeyStore, IdentitySettingsStore
    ├── sql/                 # 001_accounts.sql, 002_grants.sql, 003_signing_keys.sql, 004_settings.sql
    ├── passwords.py         # PasswordHasher (argon2id; fallback scrypt — research)
    ├── signing.py           # TokenSigner (RS256, pyjwt[crypto]) e geração de chaves
    ├── cipher.py            # SecretCipher (AES-GCM, subchave HKDF "ai-core/identity/v1")
    ├── google.py            # UpstreamOidc do Google (descoberta, troca de código, verificação do id_token)
    ├── clients_yaml.py      # ClientSource (identity.yaml do operador)
    ├── secrets_env.py       # IdentitySecrets (nomes fixos e AI_CORE_IDENTITY_SECRET_<REF>)
    └── cli.py               # `users create|list|disable|enable|password|groups`, `identity keys rotate`
```

O `api.py` não importa o resto do módulo. A 008 importa só ele; a 011 importa também `service.py` e `adapters/`.

## Protocolo

Base = `AI_CORE_PUBLIC_URL`, que é também o emissor (`iss`).

| Endpoint | Regras |
|---|---|
| `GET /.well-known/openid-configuration` | `issuer`, `authorization_endpoint` e `end_session_endpoint` a partir do endereço público; `token_endpoint`, `userinfo_endpoint`, `jwks_uri` e `revocation_endpoint` a partir do endereço pelo qual o pedido chegou (backchannel dinâmico, como o `KC_HOSTNAME_BACKCHANNEL_DYNAMIC` da Fase 7) |
| `GET /oauth2/authorize` | Só `response_type=code`; `scope` contém `openid`; `redirect_uri` exato; PKCE `S256` obrigatório para cliente público, opcional para confidencial; `state`, `nonce`, `prompt=login\|none`. Sessão válida emite código; senão, mostra o login |
| `POST /oauth2/login` | Formulário com o id do pedido pendente, token CSRF e credenciais; verificação de senha fora do laço de eventos; bloqueio (FR-013); senha temporária leva ao formulário de troca |
| `POST /oauth2/password` | Troca de senha obrigatória (senha temporária) |
| `GET/POST /oauth2/account` | "Minha conta": troca da própria senha com a senha atual (FR-022); exige sessão no provedor; encerra as outras sessões |
| `GET /oauth2/google/start`, `GET /oauth2/google/callback` | OIDC com o Google (state, nonce, PKCE); `id_token` verificado pelo JWKS do Google; regras da FR-008 |
| `POST /oauth2/token` | `authorization_code` (confidencial: `client_secret_basic` ou `client_secret_post`; público: `none` + PKCE) e `refresh_token` (FR-006) |
| `GET /oauth2/userinfo` | `sub`, `preferred_username`, `email`, `email_verified`, `name`, `groups` |
| `GET /oauth2/jwks` | Chaves ativas e em retirada |
| `POST /oauth2/revoke` | RFC 7009 |
| `GET /oauth2/logout` | `id_token_hint` e `post_logout_redirect_uri` exato; encerra a sessão e revoga os tokens de renovação dela |

Fora do subconjunto: fluxo implícito e híbrido, registro dinâmico, consentimento, `client_credentials`, device flow,
introspecção.

## Tokens

- **Acesso:** JWT RS256 com `kid`, 10 min. Claims: `iss`, `aud` (do cliente: `ai-core` para o Open WebUI,
  `ai-core-admin` para a console — ADR-031), `sub` (id estável da conta), `preferred_username`, `groups`, `azp`,
  `scope`, `iat`, `exp`. A 003 usa `preferred_username` como subject (`user:<nome>`), como na Fase 7.
- **Identidade:** acrescenta `nonce`, `auth_time`, `amr` (`pwd` ou `google`), `email`, `email_verified`, `name`.
- **Renovação:** 32 bytes aleatórios, guardado só o hash, preso à sessão (absoluta de 30 dias — clarificação de 2026-10-13). Público: rotação a cada uso
  com detecção de reuso (revoga a família). Confidencial: sem rotação (o Open WebUI renova em paralelo).
- **Código:** 60 s, uso único; reuso revoga o que saiu dele.

## Contas, senhas e grupos

- Nome de usuário `[a-z0-9][a-z0-9._-]{0,63}`, imutável, nunca reaproveitado; o mesmo padrão para grupos.
- E-mail normalizado (minúsculas, sem espaços), único.
- Senha de 12 a 128 caracteres (NIST 800-63B), argon2id com parâmetros do RFC 9106, re-hash no login quando os
  parâmetros mudam. Usuário inexistente passa por um hash fictício (tempo igual).
- Senha definida por admin é temporária (`must_change_password`).
- O grupo de administração vem de `api_keys.admin_group` do `assistants.yaml` (a 011 o lê e o passa a este módulo);
  protegido (FR-011).

## Google

- Variáveis: `AI_CORE_GOOGLE_CLIENT_ID`, `AI_CORE_GOOGLE_CLIENT_SECRET` e, opcional, `AI_CORE_GOOGLE_HOSTED_DOMAIN`, pela
  porta `IdentitySecrets` (nomes fixos, ADR-020).
- Ajuste de runtime `google_enabled` (seam Login Settings); `AI_CORE_GOOGLE_LOGIN=on|off` na instalação prevalece
  (ADR-033).
- Endereço de retorno a registrar no Google: `{AI_CORE_PUBLIC_URL}/oauth2/google/callback` (a administração o mostra).

## Sessão, CSRF e página

- Cookie `__Host-aic_session` (ou `aic_session` sem HTTPS, `AI_CORE_COOKIE_SECURE=false` em desenvolvimento), httpOnly,
  `SameSite=Lax`, só `Max-Age` — nunca `Expires`, porque o relógio fixo do perfil `test` o tornaria vencido —, id trocado
  no login.
- CSRF: token sincronizador guardado no pedido de autorização pendente, mais conferência de `Origin`.
- CSP `default-src 'self'; frame-ancestors 'none'; form-action 'self'`; CSS como arquivo estático; nenhum script inline.
  A página usa os mesmos tokens visuais da console (013) e segue o tema do sistema (`prefers-color-scheme`), sem
  botão — não há script na página.

## Chaves de assinatura

- RSA-2048, RS256 (obrigatório no OIDC; aceito pelo `JwksOidcVerifier` da 003 e pelo Open WebUI).
- Gerada no primeiro boot com identidade ligada; privada cifrada com `SecretCipher` (AES-GCM, subchave HKDF de
  `AI_CORE_MASTER_KEY`); estados ativa → em retirada → retirada; o JWKS publica ativa e em retirada por pelo menos o TTL
  do token de acesso mais a tolerância de relógio da 003.
- `ai-core identity keys rotate` (normal) e `--force` (chave mestra perdida: descarta as chaves e encerra as sessões).

## Clientes (`identity.yaml`, `AI_CORE_IDENTITY_CLIENTS_FILE`)

```yaml
clients:
  open-webui:
    type: confidential
    secret: open_webui            # → AI_CORE_IDENTITY_SECRET_OPEN_WEBUI
    audience: ai-core
    redirect_uris: [http://localhost:3000/oauth/oidc/callback]
    post_logout_redirect_uris: [http://localhost:3000/auth]
  console:
    type: public
    audience: ai-core-admin
    redirect_uris: [http://localhost:8080/callback]
    post_logout_redirect_uris: [http://localhost:8080/]
```

## Admin inicial

- `ai-core users create <nome> --email … --group <admin> [--password-stdin]` (sem a opção, pede a senha sem eco).
- `AI_CORE_BOOTSTRAP_ADMIN_USERNAME`, `_EMAIL` e `_PASSWORD_FILE`: aplicadas só com zero contas; havendo contas, aviso.

## Configuração (lida pela 011)

`AI_CORE_DISPLAY_NAME` (nome da instalação; padrão neutro provisório "Agentic"), `AI_CORE_LOGO_FILE` (opcional,
SVG ou PNG montado), `AI_CORE_PUBLIC_URL`, `AI_CORE_IDENTITY_ENABLED`, `AI_CORE_IDENTITY_CLIENTS_FILE`, `AI_CORE_IDENTITY_SECRET_<REF>`,
`AI_CORE_MASTER_KEY`, `AI_CORE_GOOGLE_*`, `AI_CORE_BOOTSTRAP_ADMIN_*`, `AI_CORE_TRUSTED_PROXIES`,
`AI_CORE_COOKIE_SECURE`. Identidade ligada junto com `AI_CORE_OIDC_ISSUER` é erro de configuração (ADR-030).

## Persistência

Schema `identity` ([ADR-015](../../docs/adr/ADR-015-persistencia-postgres-por-modulo.md)), migrações numeradas no
adapter. Expurgo periódico de pedidos pendentes, códigos, sessões e tokens vencidos (tarefa do ciclo de vida, 011).

## Portas e adapters **[ADR-012]**

| Porta | Tipo | Adapters por fase | Teste |
|---|---|---|---|
| `AccountAdmin` | primária (seam) | `service.py` | conformidade: cadastro, grupos, proteção do grupo de admin, desativação |
| `LoginSettings` | primária (seam) | `service.py` | precedência instalação > runtime; não liga sem cliente Google |
| `PublicKeySet` | primária (seam) | `service.py` | chaves ativas e em retirada |
| protocolo OIDC | primária (adapter HTTP) | `adapters/http.py` | RP de teste (authlib, só em dev) + suíte adversarial |
| `AccountStore` | secundária | memória → Postgres (Fase 9) | conformidade memória + Postgres |
| `GrantStore` (pedidos, códigos, sessões, renovação) | secundária | memória → Postgres (Fase 9) | conformidade memória + Postgres |
| `SigningKeyStore` | secundária | memória → Postgres (Fase 9) | conformidade memória + Postgres |
| `IdentitySettingsStore` | secundária | memória → Postgres (Fase 9) | conformidade memória + Postgres |
| `LoginAttempts` | secundária | memória (processo único) | em memória, relógio fixo |
| `PasswordHasher` | secundária | argon2id | hasher rápido de teste |
| `TokenSigner` | secundária | RS256 | chave de teste |
| `SecretCipher` | secundária | AES-GCM + HKDF | chave fixa de teste |
| `UpstreamOidc` | secundária | Google | provedor simulado |
| `ClientSource` | secundária | `identity.yaml` | em memória |
| `IdentitySecrets` | secundária | ambiente (`memory`, `persistent`); memória (`test`) | em memória |
| `Clock`, `TokenGenerator` | secundária | sistema; `secrets` | relógio fixo; sequência |

Import-linter: `identity.api`, `domain`, `ports` e `service` não importam `jwt`, `cryptography`, `argon2`, `httpx`,
`psycopg`, `fastapi` nem `starlette`; outros módulos importam só `identity.api`.

## Para o research do plano

- Protocolo próprio sobre `pyjwt[crypto]` (recomendado) ou servidor do authlib.
- Wheels do `argon2-cffi` para Python 3.14 em ARM64; senão, `hashlib.scrypt`.
- Parâmetros do Open WebUI v0.12 para OIDC: método de autenticação no token, PKCE, e-mail obrigatório, renovação,
  `OAUTH_MERGE_ACCOUNTS_BY_EMAIL` para religar contas criadas com o Keycloak.
