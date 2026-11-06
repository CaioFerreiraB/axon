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

## Impacto ambiental (009 US9; ADR-056)

`GET /impact?from=2026-07-16&to=2026-10-13&tz=America/Sao_Paulo&grain=week&by=model&origin=production` →

```json
{"enabled": true,
 "query": {"from": "2026-07-16", "to": "2026-10-13", "tz": "America/Sao_Paulo", "grain": "week", "by": "model",
           "origin": "production"},
 "method": {"ecologits_version": "0.11.3", "tree_kg_co2e": "140", "tree_years": 20},
 "clipped_from": null,
 "totals": {"metrics": {"gwp_kgco2eq": {"min": "0.21", "max": "0.63", "mean": "0.42"}, "energy_kwh": {…}, …},
            "coverage": {"calls": 17900, "eligible": 17256, "estimated": 16612, "approximate": 1906,
                         "unestimated": 644},
            "responses": 9790, "estimated_responses": 9600, "estimated_output_tokens": 8700000, "trees": "0.003"},
 "previous_totals": {…},
 "buckets": [{"start": "2026-07-16", "end": "2026-07-19", "calls": 512, "responses": 280, "estimated_responses": 274,
              "metrics": {…}, "rows": [{…}]}],
 "rows": [{"key": "openrouter/z-ai/glm-5.3-flash", "impact_model": "mistralai/zai-glm-5-3", "match": "approximate",
           "calls": 1980, "responses": 1090, "estimated_responses": 1090, "estimated_output_tokens": 980000,
           "coverage": {…}, "metrics": {…}}]}
```

`metrics` tem as onze grandezas — `energy_kwh`, `gwp_kgco2eq`, `adpe_kgsbeq`, `pe_mj`, `wcf_l` e `gwp_usage`,
`gwp_embodied`, `adpe_usage`, `adpe_embodied`, `pe_usage`, `pe_embodied` —, cada uma `{"min", "max", "mean"}` em texto
decimal sem expoente, com 6 algarismos significativos (R65). Padrões: os últimos 30 dias no fuso da instalação,
`grain=day`, `by=model`, `origin=production`. `grain` em `day`, `week` (ISO, segunda), `month`, `quarter`, `semester`;
`day` vai até 366 dias (`422`, `param: "grain"`); nos outros grãos, o início antes da retenção é recortado e
`clipped_from` diz o primeiro dia guardado. Outros parâmetros inválidos → `422` com `param` (`from`, `to`, `tz`, `by`,
`origin`). Estimativa desligada pela instalação → `200` com `enabled: false`, `method.ecologits_version: null`,
`totals`/`previous_totals` nulos e listas vazias.

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


## Incremento 9.7 (2026-11-05): escopos, contas por chave e apagar conta (US13; ADR-057, ADR-058; research R66–R70)

**Quem entra.** Token da console: só o grupo de administração, como antes. Chave: nas rotas de contas, grupos e `me`
(`/users*`, `/groups*`, `GET /me`), o escopo `users` **ou** a administração (grupo e escopo `admin`); em todas as demais,
só a administração. Sem isso → `404` de rota inexistente, antes de qualquer seam. A chave `users` lê tudo, inclusive as
contas e o grupo de administração; só as escritas neles são recusadas (clarificação Q2).

**Erros novos**

| Status | `code` | Quando |
|---|---|---|
| 403 | `actor_not_allowed` | ator sem administração escrevendo no grupo de administração ou numa conta dele (`param` = `username`, `groups`, `group`, `name` ou `members`) |
| 503 | `deletion_incomplete` | algum módulo falhou no apagamento da conta; `Retry-After: 5` e o relatório parcial em `report` (ao lado de `error`) |

**Rotas novas**

| Rota | Corpo | Resposta |
|---|---|---|
| `DELETE /users/{username}` | — | `200` relatório (data-model, "Relatório do apagamento"); própria conta → `422` `param: "username"`; último admin → `409 protected_group`; inexistente → `404`; incompleto → `503 deletion_incomplete` |
| `PUT /users/{username}/groups/{group}` | nenhum (corpo não vazio → `422`) | `200` `Account` já no grupo; repetir devolve o mesmo |
| `DELETE /users/{username}/groups/{group}` | nenhum | `200` `Account` fora do grupo; repetir devolve o mesmo |

Conta ou grupo inexistente → `404`.

**Campos novos**: `GET /me` → `"scopes": ["users"]` (chave) ou `null` (console); `POST /keys` aceita `"scopes":
["inference", "users"]` (ausente → `["inference"]`; `admin`, desconhecido ou vazio → `422` `param: "scopes"`); toda
visão de chave traz `"scopes"`.

Conformidade: `tests/http/contract/test_admin_scopes.py` (quem entra, cen. 1, 2, 5 e 9), `test_admin_accounts_delete.py`
(cen. 6–8) e `test_admin_scopes_adversarial.py` (SC-013: cada escrita que toca o grupo de administração com uma chave
`users` → 403 sem mudança; cada outra rota de `/admin/v1` → 404).


**Incremento 9.7, toque de 2026-11-05 (FR-054, R72)**: `Account` ganha `deleting` (`false`; `true` depois de um
apagamento incompleto, até que um `DELETE` o conclua).
