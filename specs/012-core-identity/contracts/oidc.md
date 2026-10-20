# Contrato — protocolo OIDC da plataforma

Base pública = `AXON_PUBLIC_URL` (sem barra final), que é o `iss`. Subconjunto fechado (FR-004): só
`response_type=code`; nada de implícito, híbrido, registro dinâmico, consentimento, `client_credentials`, device flow,
introspecção.

## `GET /.well-known/openid-configuration`

```json
{
  "issuer": "https://agentic.exemplo.org",
  "authorization_endpoint": "https://agentic.exemplo.org/oauth2/authorize",
  "end_session_endpoint": "https://agentic.exemplo.org/oauth2/logout",
  "token_endpoint": "<base do pedido>/oauth2/token",
  "userinfo_endpoint": "<base do pedido>/oauth2/userinfo",
  "jwks_uri": "<base do pedido>/oauth2/jwks",
  "revocation_endpoint": "<base do pedido>/oauth2/revoke",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "subject_types_supported": ["public"],
  "id_token_signing_alg_values_supported": ["RS256"],
  "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
  "code_challenge_methods_supported": ["S256"],
  "scopes_supported": ["openid", "profile", "email", "groups", "offline_access"],
  "claims_supported": ["sub", "preferred_username", "name", "email", "email_verified", "groups"]
}
```

"Base do pedido" = esquema e host pelos quais a descoberta chegou (research R8); cabeçalhos `X-Forwarded-*` só de
`AXON_TRUSTED_PROXIES`.

## `GET /oauth2/authorize`

| Parâmetro | Regra |
|---|---|
| `client_id` | cliente do `identity.yaml`; desconhecido → **página de erro**, sem redirecionar |
| `redirect_uri` | igual, byte a byte, a um dos `redirect_uris` do cliente; senão → página de erro, sem redirecionar |
| `response_type` | `code`; outro → redireciona com `error=unsupported_response_type` |
| `scope` | contém `openid`; demais ignorados se desconhecidos |
| `state` | devolvido como veio |
| `nonce` | obrigatório; vai ao token de identidade |
| `code_challenge`, `code_challenge_method` | `S256` obrigatório para cliente público (`invalid_request` sem ele); opcional para confidencial |
| `prompt` | `login` força a página; `none` sem sessão → `error=login_required` |

Com sessão válida e conta ativa sem senha temporária: redireciona com `code` e `state`. Senão: grava o pedido pendente
e mostra o login ([pages.md](pages.md)).

## `POST /oauth2/login` · `POST /oauth2/password` · `GET /oauth2/google/start` · `GET /oauth2/google/callback`

Formulários e fluxo em [pages.md](pages.md). Sucesso: cria a sessão, seta o cookie e redireciona ao `redirect_uri` do
pedido pendente com `code` e `state`.

## `POST /oauth2/token`

`application/x-www-form-urlencoded`. Autenticação do cliente: confidencial por `client_secret_basic` ou
`client_secret_post` (comparação em tempo constante); público por `client_id` + PKCE (`none`).

| `grant_type` | Regras |
|---|---|
| `authorization_code` | `code` válido, não usado, do mesmo cliente e `redirect_uri`; `code_verifier` confere o `code_challenge` (S256) quando houve desafio; reuso → `invalid_grant` e revogação dos tokens emitidos a partir do código |
| `refresh_token` | token ativo da mesma sessão e cliente, sessão não vencida nem revogada, conta ativa; público: rotaciona, e reuso de token já rotacionado revoga a família (`invalid_grant`) |

Resposta `200`:

```json
{"access_token": "<JWT>", "token_type": "Bearer", "expires_in": 600,
 "id_token": "<JWT>", "refresh_token": "<opaco>", "scope": "openid profile email groups"}
```

Erros no formato RFC 6749 (`invalid_request`, `invalid_client` 401, `invalid_grant`, `unsupported_grant_type`), com
`Cache-Control: no-store`.

### Token de acesso (JWT RS256, `kid` no cabeçalho)

```json
{"iss": "https://agentic.exemplo.org", "aud": "ai-core", "sub": "5f1c…", "preferred_username": "ana",
 "groups": ["admin", "equipe"], "azp": "open-webui", "scope": "openid profile email groups",
 "iat": 1791945600, "exp": 1791946200}
```

`aud` é a `audience` do cliente (`axon-ai` para o Open WebUI, `ai-core-admin` para a console — ADR-031).

### Token de identidade

Acrescenta `nonce`, `auth_time`, `amr`, `email`, `email_verified` (sempre `true`: o e-mail é cadastrado por admin),
`name`; `aud` = `client_id`.

## `GET /oauth2/userinfo`

`Authorization: Bearer <access_token>` válido deste emissor → `sub`, `preferred_username`, `name`, `email`,
`email_verified`, `groups`. Conta desativada → `401`.

## `GET /oauth2/assets/identity.<hash>.css` · `GET /oauth2/assets/logo`

CSS das páginas e o logotipo da instalação (`AXON_LOGO_FILE`, SVG ou PNG; sem ele, `404` e a página mostra só o
nome). `Cache-Control: public, max-age=31536000, immutable` no CSS com hash; `max-age=3600` no logotipo; SVG servido
com `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'` para não executar script embutido.

## `GET /oauth2/jwks`

O conjunto do seam `PublicKeySet`; `Cache-Control: public, max-age=300`.

## `POST /oauth2/revoke`

RFC 7009: revoga um token de renovação do cliente autenticado; sempre `200`.

## `GET /oauth2/logout`

`id_token_hint` (assinatura deste emissor; expiração tolerada), `post_logout_redirect_uri` igual a um do cliente,
`state`. Encerra a sessão do cookie e revoga os tokens de renovação dela; redireciona, ou mostra "Você saiu" sem URI
válida.

## Cabeçalhos em todas as respostas do protocolo

`Cache-Control: no-store` (exceto JWKS e CSS); páginas HTML com
`Content-Security-Policy: default-src 'none'; style-src 'self'; img-src 'self' data:; form-action 'self' <origens dos redirect_uris dos clientes>; frame-ancestors 'none'; base-uri 'none'`
(as origens vêm do `identity.yaml` no boot; sem elas, o navegador bloquearia o redirecionamento que segue o POST do
login — research R5),
`X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` (com `no-referrer`, o Chromium manda `Origin: null` no POST do próprio formulário — research R18).

## Suíte de protocolo (`tests/identity/integration/test_protocol.py`)

Com o authlib como RP sobre o app em processo: descoberta, código + PKCE, validação do token de identidade (iss, aud,
nonce, kid), userinfo, renovação com rotação, reuso de renovação, revogação, logout. Adversariais (SC-002):
`redirect_uri` divergente, cliente público sem PKCE, código reusado, formulário sem CSRF, bloqueio, e-mail Google não
verificado, conta desconhecida ou desativada, conta Google diferente da vinculada, renovação reusada.
