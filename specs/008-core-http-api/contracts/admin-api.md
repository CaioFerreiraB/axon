# Contrato — API de administração (`/admin/v1`, Fase 9)

Superfície `admin` (ADR-031): `Authorization: Bearer <token da console (aud axon-admin) | chave de API>`. Só o grupo
de administração alcança; credencial inválida → `401`; autenticado fora do grupo → `404` em **toda** rota, igual a rota
inexistente (FR-024). Toda resposta: `Cache-Control: no-store`, o identificador da requisição (FR-010) e nenhum valor de
segredo (FR-027). Sem CORS (FR-028). A console (013) espelha estes formatos em esquemas `zod`.

## Erros

Envelope da API: `{"error": {"message": "...", "type": "...", "code": "...", "param": "<campo>|null"}}`.

| Status | `code` | Quando |
|---|---|---|
| 401 | `invalid_credential` | credencial ausente, inválida, vencida ou de outra audiência |
| 404 | `not_found` | não admin; recurso inexistente |
| 409 | `version_conflict` | `version` desatualizada (corpo traz `current_version`) |
| 409 | `key_revoked` | rotação de chave revogada (`param` = `key_id`; ADR-040) |
| 409 | `installation_defined` | campo definido pela instalação (`param` = campo) |
| 409 | `master_key_missing` | gravar segredo sem `AXON_MASTER_KEY` |
| 409 | `protected_group` | apagar o grupo de administração, ou deixá-lo sem admin ativo |
| 409 | `google_not_configured` | ligar o Google sem cliente na instalação |
| 422 | `invalid_field` | validação (`param` = campo, `message` = motivo devolvido pelo módulo dono) |
| 503 | `storage_unavailable` | armazenamento fora do ar (FR-021) |

Escritas de recursos versionados levam `version` no corpo (ou na query, no `DELETE`); `null` quando ainda não existe.

## Identidade da sessão

`GET /me` → `200`

```json
{"subject": "user:ana", "username": "ana", "name": "Ana Souza", "groups": ["admin", "equipe"], "scheme": "oidc",
 "instance": {"name": "Instituto Exemplo", "logo_url": "/oauth2/assets/logo", "custom": true}}
```

`logo_url` é `null` sem logotipo. O nome vem de `AXON_DISPLAY_NAME` (011; padrão "Axon"); a console usa os dois na barra
lateral (013 FR-020). `custom` (aditivo, US10, ADR-038) é `true` quando a instalação definiu um nome diferente de "Axon"
ou um logotipo servido; com `false`, o lugar principal é o lockup Axon e a atribuição "com Axon" não aparece. Sem marca
própria: `{"name": "Axon", "logo_url": null, "custom": false}`.

## Assistants de sistema (003, `SystemAssistantAdmin`)

| Rota | Corpo | Resposta |
|---|---|---|
| `GET /assistants` | — | `{"data": [AssistantView…]}` |
| `GET /assistants/{name}` | — | `AssistantView` |
| `PUT /assistants/{name}/models` | `{"roles": {"generation": "openrouter/openai/gpt-4.1-mini", "controller": "…"}, "version": 3}` — a seção inteira (003 FR-018): papel ausente fica sem modelo | `AssistantView` |
| `PUT /assistants/{name}/mcp` | `{"aliases": ["arquivos"], "allowed": ["arquivos.listar"], "write": [], "version": null}` | `AssistantView` |
| `PUT /assistants/{name}/auth` | `{"schemes": ["oidc", "api_key"], "allow": ["svc:relatorios", "group:equipe"], "version": null}` — a seção inteira (003 FR-031, ADR-040); só com `auth` em `overrides` | `AssistantView` |
| `DELETE /assistants/{name}/overrides/{models\|mcp\|auth}?version=3` | — | `AssistantView` |
| `GET /assistants/{name}/history` | — | `{"data": [{"section", "action", "payload", "version", "actor", "at"}…]}` |
| `POST /assistants/{name}/models/check` | `{"role": "generation", "model": "openrouter/openai/gpt-4.1-mini"}` | `{"available": true, "detail": "respondeu", "latency_ms": 412}` — pela verificação de saúde do Model Router (006); modelo fora da allowlist → `422` |
| `GET /providers` | — | `{"data": [{"name": "ollama", "ready": false, "detail": "provider inalcançável em http://localhost:11434/v1", "reports_cost": false}, {"name": "openrouter", "ready": true, "detail": null, "reports_cost": true}]}` — os providers registrados, por nome, pelo `ModelRouting.providers()` da 006: o remoto pronto pela credencial, o local se responde (ADR-035); `reports_cost`, se informa o custo de cada chamada (ADR-036) |

`AssistantView`:

```json
{"name": "geral", "description": "Uso geral, com ferramentas", "visibility": "public", "flow": "agentic",
 "status": {"available": true, "reasons": []},
 "overridable": ["models", "mcp"], "required_roles": ["generation", "controller"], "allow": ["openrouter/*"],
 "yaml": {"models": {"generation": "openrouter/openai/gpt-4.1-nano", "controller": "openrouter/openai/gpt-4.1-nano"},
          "mcp": {"aliases": ["arquivos", "agenda"], "allowed": ["arquivos.listar"], "write": []},
          "auth": {"schemes": ["oidc"], "allow": ["group:equipe"]}},
 "overrides": [{"section": "models", "state": "active", "reason": null, "version": 3,
                "updated_by": "user:ana", "updated_at": "2026-10-07T17:32:00Z",
                "payload": {"generation": "openrouter/openai/gpt-4.1-mini", "controller": "openrouter/openai/gpt-4.1-nano"}}],
 "effective": {"models": {"generation": "openrouter/openai/gpt-4.1-mini", "controller": "openrouter/openai/gpt-4.1-nano"},
               "mcp": {"aliases": ["arquivos", "agenda"], "allowed": ["arquivos.listar"], "write": []},
               "auth": {"schemes": ["oidc"], "allow": ["group:equipe"]}}}
```

`yaml.auth` e `effective.auth` vêm sempre, também sem `auth` em `overridable` (só leitura). O `payload` de uma
sobreposição ou de uma linha do histórico de `auth` é `{"schemes": [...], "allow": [...]}` (ADR-040).

## Servidores MCP globais (007)

`GET|POST /mcp`, `GET|PUT|DELETE /mcp/{alias}`, `GET /mcp/{alias}/health` — os mesmos formatos da superfície privada
(`contracts/mcp-routes.md`), montados também aqui; a saúde devolve as tools descobertas (a console as usa na aba MCP).

## Uso e preços (009)

`GET /usage?from=2026-09-14&to=2026-10-13&tz=America/Sao_Paulo&by=model&origin=production` →

```json
{"query": {…}, "currency": "USD",
 "totals": [{"key": "openrouter/openai/gpt-4.1-mini", "calls": 3118, "requests": 1802, "input_tokens": 11400000,
             "output_tokens": 1900000, "cost": "33.520000", "priced": true}],
 "total_cost": "41.870000", "incomplete": true, "previous_total_cost": "38.690000",
 "days": [{"day": "2026-09-14", "requests": 61, "rows": [ … ]}]}
```

Valores monetários como string decimal. `tz` padrão: `AXON_USAGE_TIMEZONE`. `by` padrão `model`; `origin` padrão
`production`; período padrão: últimos 30 dias no fuso. `requests` de cada dia são as requisições distintas do dia
(ADR-036): por modelo, somar as linhas contaria duas vezes a requisição que usa dois modelos.

| Rota | Corpo | Resposta |
|---|---|---|
| `GET /prices` | — | `{"data": [{"provider", "model", "input", "output", "effective_from", "state", "created_by", "created_at"}…]}` |
| `POST /prices` | `{"provider": "ollama", "model": "qwen3:1.7b", "input": "0", "output": "0", "effective_from": "2026-09-14"}` | `201` + o preço; `422` com `param: "provider"` se o provider informa o custo de cada chamada (ADR-036) |
| `GET /prices/unpriced?from&to` | — | `{"data": ["ollama/qwen3:1.7b"]}` |

O custo de uma linha é o que o provider informou nas chamadas (o OpenRouter informa) mais, pelo preço vigente, os tokens
das chamadas sem custo informado (ADR-035). Um modelo só aparece em `unpriced` quando sobram tokens sem custo informado.
Provider que informa o custo não ganha preço novo (ADR-036): as chamadas dele sem custo informado (anteriores ao ADR-035)
ficam como custo não informado, e os preços já gravados continuam valendo para elas.

## Observabilidade (009)

| Rota | Corpo | Resposta |
|---|---|---|
| `GET /observability` | — | `{"langfuse": {"enabled", "host", "public_key", "secret_set", "sources": {"host": "installation"…}}, "capture_content": false, "capture_source": "default", "version": 4, "health": [{"name": "langfuse", "state", "dropped_24h", "last_error", "last_sent_at"}…]}` |
| `PUT /observability/langfuse` | `{"enabled"?, "host"?, "public_key"?, "secret_key"?, "version"}` | a mesma visão; nunca o segredo |
| `PUT /observability/capture` | `{"enabled": true, "acknowledged": true, "version": 4}` | a mesma visão; ligar sem `acknowledged: true` → `422` (`param: acknowledged`) |
| `POST /observability/langfuse/test` | `{"host"?, "public_key"?, "secret_key"?}` | `{"ok": true, "detail": "projeto agentic"}` |

## Contas, grupos e login (012)

| Rota | Corpo | Resposta |
|---|---|---|
| `GET /users?query&state=active\|disabled\|all&limit&cursor` | — | `{"data": [Account…], "next_cursor": "…"}` |
| `POST /users` | `{"username", "email", "name", "groups": [], "google_only": false}` | `201` `{"account": Account, "temporary_password": "k7m2-qx9p-…"}` (sem a senha se `google_only`) |
| `GET /users/{username}` | — | `Account` |
| `PATCH /users/{username}` | `{"email"?, "name"?, "groups"?, "version"}` | `Account` |
| `POST /users/{username}/password` | — | `{"account": Account, "temporary_password": "…"}` |
| `POST /users/{username}/disable` · `/enable` | — | `Account` |
| `DELETE /users/{username}/google` | — | `Account` |
| `GET /groups` | — | `{"data": [{"name", "members", "protected"}…]}` |
| `POST /groups` | `{"name"}` | `201` + o grupo |
| `DELETE /groups/{name}` | — | `204` |
| `PUT /groups/{name}/members` | `{"usernames": []}` | o grupo |
| `GET /login-settings` | — | `{"google_enabled", "google_source", "google_configured", "google_redirect_uri", "google_client_id", "google_hosted_domain", "version"}` |
| `PUT /login-settings` | `{"google_enabled": true, "version": 2}` | a mesma visão |

`Account` = os campos do `Account` da 012 (`id`, `username`, `email`, `name`, `groups`, `active`,
`temporary_password`, `has_password`, `google_linked`, `created_at`, `updated_at`, `updated_by`, `last_login_at`,
`version`). A senha temporária só aparece na resposta que a definiu.

## Chaves de API (003) e saúde (011)

`GET /keys`, `POST /keys`, `DELETE /keys/{key_id}` — os formatos da superfície privada; `GET /health` — a saúde agregada.

Fase 9 (2026-10-21; ADR-040, US11):

| Rota | Corpo | Resposta |
|---|---|---|
| `POST /keys/{key_id}/rotate` | nenhum (objeto vazio aceito; qualquer campo → 422) | `200` `{"key_id", "subject", "groups", "label", "created_at", "revoked_at": null, "rotated_at": "…", "key": "axn_<key_id>_…"}` — a única resposta, além da emissão, com a chave em claro; inexistente → `404`; revogada → `409 key_revoked` |

A chave, nas duas superfícies, ganha `rotated_at` (`null` se nunca rotacionada). Na emissão, `svc:<nome>` fora do padrão
dos nomes de Assistant → `422` `param: "subject"`; o grupo de administração em `groups` → `422` `param: "groups"` (só a
CLI o concede). O seletor de `allow` da console usa `GET /keys` e `GET /groups`: não há rota própria.

## Conformidade (`tests/http/contract/test_admin_api.py`)

Para cada rota: admin por token da console e por chave → sucesso; não admin → `404` idêntico ao de rota inexistente;
token do chat → `401`; nenhuma resposta com valor de segredo (varredura); `409`/`422` com `param`; `Cache-Control:
no-store`.
